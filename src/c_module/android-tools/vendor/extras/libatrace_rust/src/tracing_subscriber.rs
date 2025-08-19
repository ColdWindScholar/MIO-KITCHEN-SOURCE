// Copyright (C) 2023 The Android Open Source Project
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

//! Tracing-subscriber layer for libatrace_rust.

use ::atrace::AtraceTag;
use std::fmt::Write;
use tracing::span::Attributes;
use tracing::span::Record;
use tracing::{Event, Id, Subscriber};
use tracing_subscriber::field::Visit;
use tracing_subscriber::layer::{Context, Layer};
use tracing_subscriber::registry::LookupSpan;

/// Subscriber layer that forwards events to ATrace.
pub struct AtraceSubscriber {
    tag: AtraceTag,
    should_record_fields: bool,
    should_filter: bool,
}

impl Default for AtraceSubscriber {
    fn default() -> Self {
        Self::new(AtraceTag::App)
    }
}

impl AtraceSubscriber {
    /// Makes a new subscriber with tag.
    pub fn new(tag: AtraceTag) -> AtraceSubscriber {
        AtraceSubscriber { tag, should_filter: false, should_record_fields: true }
    }

    /// Enables event and span filtering. With filtering enabled, this layer would filter events for
    /// all the layers of the subscriber.
    /// Use this to speed up the subscriber if it's the only layer. Do not enable if you need other
    /// layers to receive events when ATrace is disabled.
    pub fn with_filter(self) -> AtraceSubscriber {
        AtraceSubscriber { should_filter: true, ..self }
    }

    /// Disables recording of field values.
    pub fn without_fields(self) -> AtraceSubscriber {
        AtraceSubscriber { should_record_fields: false, ..self }
    }
}

// Internal methods.
impl AtraceSubscriber {
    /// Checks that events and spans should be recorded in the span/event notification.
    fn should_process_event(&self) -> bool {
        // If `should_filter == true` we don't need to check the tag - it was already checked by
        // the layer filter in the `Layer::enabled()` method.
        // The checks are done in this order:
        //  * `Layer::register_callsite()` - once per callsite, the result is cached.
        //  * `Layer::enabled()` - once per span or event construction if the callsite is enabled.
        //  * `should_process_event()` - on every notification like new span, span enter/exit/record, event.
        // The first two checks are global, i.e. affect other layers, and only enabled with `should_filter`.
        // Read more:
        // https://docs.rs/tracing-subscriber/latest/tracing_subscriber/layer/index.html#filtering-with-layers
        self.should_filter || atrace::atrace_is_tag_enabled(self.tag)
    }
}

impl<S: Subscriber + for<'lookup> LookupSpan<'lookup>> Layer<S> for AtraceSubscriber {
    fn register_callsite(
        &self,
        _metadata: &'static tracing::Metadata<'static>,
    ) -> tracing::subscriber::Interest {
        if self.should_filter {
            // When we return `Interest::sometimes()`, the `enabled()` method would get checked
            // every time.
            // We can't use callsite caching (`Interest::never()`) because there's no callback
            // for when tracing gets enabled - we need to check it every time.
            tracing::subscriber::Interest::sometimes()
        } else {
            // If we do not disable events in the layer, we always receive the notifications.
            tracing::subscriber::Interest::always()
        }
    }

    // When filtering in this layer is enabled, this method would get called on every event and span.
    // This filter affects all layers, so if this method returns false, it would disable the event
    // for others as well.
    fn enabled(&self, _metadata: &tracing::Metadata<'_>, _ctx: Context<'_, S>) -> bool {
        !self.should_filter || atrace::atrace_is_tag_enabled(self.tag)
    }

    fn on_new_span(&self, attrs: &Attributes, id: &Id, ctx: Context<S>) {
        if !self.should_record_fields || attrs.fields().is_empty() || !self.should_process_event() {
            return;
        }

        let span = ctx.span(id).unwrap();
        let mut formatter = FieldFormatter::for_span(span.metadata().name());
        attrs.record(&mut formatter);
        span.extensions_mut().insert(formatter);
    }

    fn on_record(&self, span: &Id, values: &Record, ctx: Context<S>) {
        if !self.should_record_fields || !self.should_process_event() {
            return;
        }

        values
            .record(ctx.span(span).unwrap().extensions_mut().get_mut::<FieldFormatter>().unwrap());
    }

    fn on_enter(&self, id: &Id, ctx: Context<S>) {
        if !self.should_process_event() {
            return;
        }

        let span = ctx.span(id).unwrap();
        if span.fields().is_empty() || !self.should_record_fields {
            atrace::atrace_begin(self.tag, span.metadata().name());
        } else {
            let span_extensions = span.extensions();
            let formatter = span_extensions.get::<FieldFormatter>().unwrap();
            atrace::atrace_begin(self.tag, formatter.as_str());
        }
    }

    fn on_exit(&self, _id: &Id, _ctx: Context<S>) {
        if !self.should_process_event() {
            return;
        }

        atrace::atrace_end(self.tag);
    }

    fn on_event(&self, event: &Event, _ctx: Context<S>) {
        if !self.should_process_event() {
            return;
        }

        if self.should_record_fields {
            let mut formatter = FieldFormatter::for_event();
            event.record(&mut formatter);
            atrace::atrace_instant(self.tag, formatter.as_str());
        } else if let Some(field) = event.metadata().fields().field("message") {
            struct MessageVisitor<'a> {
                tag: AtraceTag,
                field: &'a tracing::field::Field,
            }
            impl Visit for MessageVisitor<'_> {
                fn record_str(&mut self, field: &tracing::field::Field, value: &str) {
                    if field == self.field {
                        atrace::atrace_instant(self.tag, value);
                    }
                }
                fn record_debug(
                    &mut self,
                    field: &tracing::field::Field,
                    value: &dyn std::fmt::Debug,
                ) {
                    if field == self.field {
                        atrace::atrace_instant(self.tag, &format!("{:?}", value));
                    }
                }
            }
            event.record(&mut MessageVisitor { tag: self.tag, field: &field });
        } else {
            atrace::atrace_instant(
                self.tag,
                &format!("{} event", event.metadata().level().as_str()),
            );
        }
    }
}

struct FieldFormatter {
    is_event: bool,
    s: String,
}

impl FieldFormatter {
    fn new() -> FieldFormatter {
        const DEFAULT_STR_CAPACITY: usize = 128; // Should fit most events without realloc.
        FieldFormatter { is_event: true, s: String::with_capacity(DEFAULT_STR_CAPACITY) }
    }

    fn for_event() -> FieldFormatter {
        FieldFormatter { is_event: true, ..FieldFormatter::new() }
    }
    fn for_span(span_name: &str) -> FieldFormatter {
        let mut formatter = FieldFormatter { is_event: false, ..FieldFormatter::new() };
        formatter.s.push_str(span_name);
        formatter
    }

    fn as_str(&self) -> &str {
        &self.s
    }
    fn add_delimeter_if_needed(&mut self) {
        if !self.s.is_empty() {
            self.s.push_str(", ");
        }
    }
}

impl Visit for FieldFormatter {
    fn record_str(&mut self, field: &tracing::field::Field, value: &str) {
        self.add_delimeter_if_needed();
        if self.is_event && field.name() == "message" {
            self.s.push_str(value);
        } else {
            write!(&mut self.s, "{} = \"{}\"", field.name(), value).unwrap();
        }
    }
    fn record_debug(&mut self, field: &tracing::field::Field, value: &dyn std::fmt::Debug) {
        self.add_delimeter_if_needed();
        if self.is_event && field.name() == "message" {
            write!(&mut self.s, "{:?}", value).unwrap();
        } else {
            write!(&mut self.s, "{} = {:?}", field.name(), value).unwrap();
        }
    }
}

#[cfg(test)]
use self::tests::mock_atrace as atrace;

#[cfg(test)]
mod tests {
    use super::*;
    use tracing::Level;
    use tracing_subscriber::prelude::__tracing_subscriber_SubscriberExt;

    pub mod mock_atrace {
        use atrace::AtraceTag;
        use std::cell::RefCell;

        /// Contains logic to check binding calls.
        /// Implement this trait in the test with mocking logic and checks in implemented functions.
        /// Default implementations panic.
        pub trait ATraceMocker {
            fn atrace_is_tag_enabled(&mut self, _tag: AtraceTag) -> bool {
                panic!("Unexpected call");
            }

            fn atrace_begin(&mut self, _tag: AtraceTag, _name: &str) {
                panic!("Unexpected call");
            }

            fn atrace_end(&mut self, _tag: AtraceTag) {
                panic!("Unexpected call");
            }

            fn atrace_instant(&mut self, _tag: AtraceTag, _name: &str) {
                panic!("Unexpected call");
            }

            /// This method should contain checks to be performed at the end of the test.
            fn finish(&self) {}
        }

        struct DefaultMocker;
        impl ATraceMocker for DefaultMocker {}

        // Global mock object is thread-local, so that the tests can run safely in parallel.
        thread_local!(static MOCKER: RefCell<Box<dyn ATraceMocker>> = RefCell::new(Box::new(DefaultMocker{})));

        /// Sets the global mock object.
        fn set_mocker(mocker: Box<dyn ATraceMocker>) {
            MOCKER.with(|m| *m.borrow_mut() = mocker)
        }

        /// Calls the passed method `f` with a mutable reference to the global mock object.
        /// Example:
        /// ```
        /// with_mocker(|mocker| mocker.atrace_begin(tag, name))
        /// ```
        fn with_mocker<F, R>(f: F) -> R
        where
            F: FnOnce(&mut dyn ATraceMocker) -> R,
        {
            MOCKER.with(|m| f(m.borrow_mut().as_mut()))
        }

        /// Finish the test and perform final checks in the mocker.
        /// Calls `finish()` on the global mocker.
        ///
        /// Needs to be called manually at the end of each test that uses mocks.
        ///
        /// May panic, so it can not be called in `drop()` methods,
        /// since it may result in double panic.
        pub fn mocker_finish() {
            with_mocker(|m| m.finish())
        }

        /// RAII guard that resets the mock to the default implementation.
        pub struct MockerGuard;
        impl Drop for MockerGuard {
            fn drop(&mut self) {
                set_mocker(Box::new(DefaultMocker {}));
            }
        }

        /// Sets the mock object for the duration of the scope.
        ///
        /// Returns a RAII guard that resets the mock back to default on destruction.
        pub fn set_scoped_mocker<T: ATraceMocker + 'static>(m: T) -> MockerGuard {
            set_mocker(Box::new(m));
            MockerGuard {}
        }

        // Wrapped functions that forward calls into mocker.

        pub fn atrace_is_tag_enabled(tag: AtraceTag) -> bool {
            with_mocker(|m| m.atrace_is_tag_enabled(tag))
        }
        pub fn atrace_begin(tag: AtraceTag, name: &str) {
            with_mocker(|m| m.atrace_begin(tag, name))
        }

        pub fn atrace_end(tag: AtraceTag) {
            with_mocker(|m| m.atrace_end(tag))
        }

        pub fn atrace_instant(tag: AtraceTag, name: &str) {
            with_mocker(|m| m.atrace_instant(tag, name))
        }
    }

    #[test]
    fn emits_span_begin() {
        #[derive(Default)]
        struct CallCheck {
            begin_count: u32,
        }
        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled(&mut self, _tag: AtraceTag) -> bool {
                true
            }
            fn atrace_begin(&mut self, tag: AtraceTag, name: &str) {
                self.begin_count += 1;
                assert!(self.begin_count < 2);
                assert_eq!(tag, AtraceTag::App);
                assert_eq!(name, "test span");
            }
            fn atrace_end(&mut self, _tag: AtraceTag) {}

            fn finish(&self) {
                assert_eq!(self.begin_count, 1);
            }
        }
        let _mock_guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        let _subscriber_guard = tracing::subscriber::set_default(
            tracing_subscriber::registry().with(AtraceSubscriber::default()),
        );

        let _span = tracing::info_span!("test span").entered();

        mock_atrace::mocker_finish();
    }

    #[test]
    fn emits_span_end() {
        #[derive(Default)]
        struct CallCheck {
            end_count: u32,
        }
        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled(&mut self, _tag: AtraceTag) -> bool {
                true
            }
            fn atrace_begin(&mut self, _tag: AtraceTag, _name: &str) {}
            fn atrace_end(&mut self, tag: AtraceTag) {
                self.end_count += 1;
                assert!(self.end_count < 2);
                assert_eq!(tag, AtraceTag::App);
            }

            fn finish(&self) {
                assert_eq!(self.end_count, 1);
            }
        }
        let _mock_guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        let _subscriber_guard = tracing::subscriber::set_default(
            tracing_subscriber::registry().with(AtraceSubscriber::default()),
        );

        {
            let _span = tracing::info_span!("test span").entered();
        }

        mock_atrace::mocker_finish();
    }

    #[test]
    fn span_begin_end_is_ordered() {
        #[derive(Default)]
        struct CallCheck {
            begin_count: u32,
            instant_count: u32,
            end_count: u32,
        }
        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled(&mut self, _tag: AtraceTag) -> bool {
                true
            }
            fn atrace_begin(&mut self, _tag: AtraceTag, _name: &str) {
                assert_eq!(self.end_count, 0);
                assert_eq!(self.instant_count, 0);

                self.begin_count += 1;
                assert!(self.begin_count < 2);
            }
            fn atrace_instant(&mut self, _tag: AtraceTag, _name: &str) {
                assert_eq!(self.begin_count, 1);
                assert_eq!(self.end_count, 0);

                self.instant_count += 1;
                assert!(self.instant_count < 2);
            }
            fn atrace_end(&mut self, _tag: AtraceTag) {
                assert_eq!(self.begin_count, 1);
                assert_eq!(self.instant_count, 1);

                self.end_count += 1;
                assert!(self.end_count < 2);
            }

            fn finish(&self) {
                assert_eq!(self.begin_count, 1);
                assert_eq!(self.end_count, 1);
                assert_eq!(self.instant_count, 1);
            }
        }
        let _mock_guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        let _subscriber_guard = tracing::subscriber::set_default(
            tracing_subscriber::registry().with(AtraceSubscriber::default()),
        );

        {
            let _span = tracing::info_span!("span").entered();
            tracing::info!("test info");
        }

        mock_atrace::mocker_finish();
    }

    #[test]
    fn emits_instant_event() {
        #[derive(Default)]
        struct CallCheck {
            instant_count: u32,
        }
        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled(&mut self, _tag: AtraceTag) -> bool {
                true
            }
            fn atrace_instant(&mut self, tag: AtraceTag, name: &str) {
                self.instant_count += 1;
                assert!(self.instant_count < 2);
                assert_eq!(tag, AtraceTag::App);
                assert_eq!(name, "test info");
            }

            fn finish(&self) {
                assert_eq!(self.instant_count, 1);
            }
        }
        let _mock_guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        let _subscriber_guard = tracing::subscriber::set_default(
            tracing_subscriber::registry().with(AtraceSubscriber::default()),
        );

        tracing::info!("test info");

        mock_atrace::mocker_finish();
    }

    #[test]
    fn formats_event_without_message_with_fields_disabled() {
        #[derive(Default)]
        struct CallCheck {
            instant_count: u32,
        }
        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled(&mut self, _tag: AtraceTag) -> bool {
                true
            }
            fn atrace_instant(&mut self, _tag: AtraceTag, name: &str) {
                self.instant_count += 1;
                assert!(self.instant_count < 2);
                assert_eq!(name, "DEBUG event");
            }

            fn finish(&self) {
                assert_eq!(self.instant_count, 1);
            }
        }
        let _mock_guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        let _subscriber_guard = tracing::subscriber::set_default(
            tracing_subscriber::registry().with(AtraceSubscriber::default().without_fields()),
        );

        tracing::debug!(foo = 1);

        mock_atrace::mocker_finish();
    }

    #[test]
    fn formats_event_without_message_with_fields_enabled() {
        #[derive(Default)]
        struct CallCheck {
            instant_count: u32,
        }
        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled(&mut self, _tag: AtraceTag) -> bool {
                true
            }
            fn atrace_instant(&mut self, _tag: AtraceTag, name: &str) {
                self.instant_count += 1;
                assert!(self.instant_count < 2);
                assert_eq!(name, "foo = 1");
            }

            fn finish(&self) {
                assert_eq!(self.instant_count, 1);
            }
        }
        let _mock_guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        let _subscriber_guard = tracing::subscriber::set_default(
            tracing_subscriber::registry().with(AtraceSubscriber::default()),
        );

        tracing::debug!(foo = 1);

        mock_atrace::mocker_finish();
    }

    #[test]
    fn can_set_tag() {
        #[derive(Default)]
        struct CallCheck {
            begin_count: u32,
            instant_count: u32,
            end_count: u32,
        }
        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled(&mut self, _tag: AtraceTag) -> bool {
                true
            }
            fn atrace_begin(&mut self, tag: AtraceTag, _name: &str) {
                self.begin_count += 1;
                assert!(self.begin_count < 2);
                assert_eq!(tag, AtraceTag::WindowManager);
            }
            fn atrace_instant(&mut self, tag: AtraceTag, _name: &str) {
                self.instant_count += 1;
                assert!(self.instant_count < 2);
                assert_eq!(tag, AtraceTag::WindowManager);
            }
            fn atrace_end(&mut self, tag: AtraceTag) {
                self.end_count += 1;
                assert!(self.end_count < 2);
                assert_eq!(tag, AtraceTag::WindowManager);
            }

            fn finish(&self) {
                assert_eq!(self.begin_count, 1);
                assert_eq!(self.end_count, 1);
                assert_eq!(self.instant_count, 1);
            }
        }
        let _mock_guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        let _subscriber_guard = tracing::subscriber::set_default(
            tracing_subscriber::registry().with(AtraceSubscriber::new(AtraceTag::WindowManager)),
        );

        {
            let _span = tracing::info_span!("span").entered();
            tracing::info!("test info");
        }

        mock_atrace::mocker_finish();
    }

    #[test]
    fn fields_ignored_when_disabled() {
        #[derive(Default)]
        struct CallCheck {
            begin_count: u32,
            instant_count: u32,
        }
        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled(&mut self, _tag: AtraceTag) -> bool {
                true
            }
            fn atrace_begin(&mut self, _tag: AtraceTag, name: &str) {
                self.begin_count += 1;
                assert!(self.begin_count < 2);
                assert_eq!(name, "test span");
            }
            fn atrace_instant(&mut self, _tag: AtraceTag, name: &str) {
                self.instant_count += 1;
                assert!(self.instant_count < 2);
                assert_eq!(name, "test info");
            }
            fn atrace_end(&mut self, _tag: AtraceTag) {}
            fn finish(&self) {
                assert_eq!(self.begin_count, 1);
                assert_eq!(self.instant_count, 1);
            }
        }
        let _mock_guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        let _subscriber_guard = tracing::subscriber::set_default(
            tracing_subscriber::registry().with(AtraceSubscriber::default().without_fields()),
        );

        let _span = tracing::info_span!("test span", bar = "foo").entered();
        tracing::event!(Level::INFO, foo = "bar", "test info");

        mock_atrace::mocker_finish();
    }

    #[test]
    fn formats_instant_event_fields() {
        #[derive(Default)]
        struct CallCheck {
            instant_count: u32,
        }
        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled(&mut self, _tag: AtraceTag) -> bool {
                true
            }
            fn atrace_instant(&mut self, _tag: AtraceTag, name: &str) {
                self.instant_count += 1;
                assert!(self.instant_count < 2);
                assert_eq!(name, "test info, foo = \"bar\", baz = 5");
            }
            fn finish(&self) {
                assert_eq!(self.instant_count, 1);
            }
        }
        let _mock_guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        let _subscriber_guard = tracing::subscriber::set_default(
            tracing_subscriber::registry().with(AtraceSubscriber::default()),
        );

        tracing::event!(Level::INFO, foo = "bar", baz = 5, "test info");

        mock_atrace::mocker_finish();
    }

    #[test]
    fn formats_span_fields() {
        #[derive(Default)]
        struct CallCheck {
            begin_count: u32,
        }
        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled(&mut self, _tag: AtraceTag) -> bool {
                true
            }
            fn atrace_begin(&mut self, _tag: AtraceTag, name: &str) {
                self.begin_count += 1;
                assert!(self.begin_count < 2);
                assert_eq!(name, "test span, foo = \"bar\", baz = 5");
            }
            fn atrace_end(&mut self, _tag: AtraceTag) {}
            fn finish(&self) {
                assert_eq!(self.begin_count, 1);
            }
        }
        let _mock_guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        let _subscriber_guard = tracing::subscriber::set_default(
            tracing_subscriber::registry().with(AtraceSubscriber::default()),
        );

        let _span = tracing::info_span!("test span", foo = "bar", baz = 5).entered();

        mock_atrace::mocker_finish();
    }
}
