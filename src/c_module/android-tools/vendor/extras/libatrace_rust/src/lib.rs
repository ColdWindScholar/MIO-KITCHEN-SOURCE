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

//! ATrace instrumentation methods from cutils.

use std::ffi::CString;

#[cfg(not(test))]
use cutils_trace_bindgen as trace_bind;

// Wrap tags into a mod to allow missing docs.
// We have to use the mod for this because Rust won't apply the attribute to the bitflags macro
// invocation.
pub use self::tags::*;
pub mod tags {
    // Tag constants are not documented in libcutils, so we don't document them here.
    #![allow(missing_docs)]

    use bitflags::bitflags;
    use static_assertions::const_assert_eq;

    bitflags! {
        /// The trace tag is used to filter tracing in userland to avoid some of the runtime cost of
        /// tracing when it is not desired.
        ///
        /// Using `AtraceTag::Always` will result in the tracing always being enabled - this should
        /// ONLY be done for debug code, as userland tracing has a performance cost even when the
        /// trace is not being recorded. `AtraceTag::Never` will result in the tracing always being
        /// disabled.
        ///
        /// `AtraceTag::Hal` should be bitwise ORed with the relevant tags for tracing
        /// within a hardware module. For example a camera hardware module would use
        /// `AtraceTag::Camera | AtraceTag::Hal`.
        ///
        /// Source of truth is `system/core/libcutils/include/cutils/trace.h`.
        #[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
        pub struct AtraceTag: u64 {
            const Never           = cutils_trace_bindgen::ATRACE_TAG_NEVER as u64;
            const Always          = cutils_trace_bindgen::ATRACE_TAG_ALWAYS as u64;
            const Graphics        = cutils_trace_bindgen::ATRACE_TAG_GRAPHICS as u64;
            const Input           = cutils_trace_bindgen::ATRACE_TAG_INPUT as u64;
            const View            = cutils_trace_bindgen::ATRACE_TAG_VIEW as u64;
            const Webview         = cutils_trace_bindgen::ATRACE_TAG_WEBVIEW as u64;
            const WindowManager   = cutils_trace_bindgen::ATRACE_TAG_WINDOW_MANAGER as u64;
            const ActivityManager = cutils_trace_bindgen::ATRACE_TAG_ACTIVITY_MANAGER as u64;
            const SyncManager     = cutils_trace_bindgen::ATRACE_TAG_SYNC_MANAGER as u64;
            const Audio           = cutils_trace_bindgen::ATRACE_TAG_AUDIO as u64;
            const Video           = cutils_trace_bindgen::ATRACE_TAG_VIDEO as u64;
            const Camera          = cutils_trace_bindgen::ATRACE_TAG_CAMERA as u64;
            const Hal             = cutils_trace_bindgen::ATRACE_TAG_HAL as u64;
            const App             = cutils_trace_bindgen::ATRACE_TAG_APP as u64;
            const Resources       = cutils_trace_bindgen::ATRACE_TAG_RESOURCES as u64;
            const Dalvik          = cutils_trace_bindgen::ATRACE_TAG_DALVIK as u64;
            const Rs              = cutils_trace_bindgen::ATRACE_TAG_RS as u64;
            const Bionic          = cutils_trace_bindgen::ATRACE_TAG_BIONIC as u64;
            const Power           = cutils_trace_bindgen::ATRACE_TAG_POWER as u64;
            const PackageManager  = cutils_trace_bindgen::ATRACE_TAG_PACKAGE_MANAGER as u64;
            const SystemServer    = cutils_trace_bindgen::ATRACE_TAG_SYSTEM_SERVER as u64;
            const Database        = cutils_trace_bindgen::ATRACE_TAG_DATABASE as u64;
            const Network         = cutils_trace_bindgen::ATRACE_TAG_NETWORK as u64;
            const Adb             = cutils_trace_bindgen::ATRACE_TAG_ADB as u64;
            const Vibrator        = cutils_trace_bindgen::ATRACE_TAG_VIBRATOR as u64;
            const Aidl            = cutils_trace_bindgen::ATRACE_TAG_AIDL as u64;
            const Nnapi           = cutils_trace_bindgen::ATRACE_TAG_NNAPI as u64;
            const Rro             = cutils_trace_bindgen::ATRACE_TAG_RRO as u64;
            const Thermal         = cutils_trace_bindgen::ATRACE_TAG_THERMAL as u64;
            const Last            = cutils_trace_bindgen::ATRACE_TAG_LAST as u64;
            const NotReady        = cutils_trace_bindgen::ATRACE_TAG_NOT_READY as u64;
            const ValidMask       = cutils_trace_bindgen::ATRACE_TAG_VALID_MASK as u64;
        }
    }

    // Assertion to keep tags in sync. If it fails, it means there are new tags added to
    // cutils/trace.h. Add them to the tags above and update the assertion.
    const_assert_eq!(AtraceTag::Thermal.bits(), cutils_trace_bindgen::ATRACE_TAG_LAST as u64);
}

/// RAII guard to close an event with tag.
pub struct ScopedEvent {
    tag: AtraceTag,
}

impl Drop for ScopedEvent {
    fn drop(&mut self) {
        atrace_end(self.tag);
    }
}

/// Begins an event via `atrace_begin` and returns a guard that calls `atrace_end` when dropped.
pub fn begin_scoped_event(tag: AtraceTag, name: &str) -> ScopedEvent {
    atrace_begin(tag, name);
    ScopedEvent { tag }
}

/// Creates a scoped event with the current method name.
#[macro_export]
macro_rules! trace_method {
    {$tag:expr} => {
        let mut _atrace_trace_method_name: &'static str = "";
        {
            // Declares function f inside current function.
            fn f() {}
            fn type_name_of<T>(_: T) -> &'static str {
                std::any::type_name::<T>()
            }
            // type name of f is struct_or_crate_name::calling_function_name::f
            let name = type_name_of(f);
            // Remove the third to last character ("::f")
            _atrace_trace_method_name = &name[..name.len() - 3];
        }
        let _atrace_trace_method_guard = atrace::begin_scoped_event($tag, _atrace_trace_method_name);
    };
}

/// Set whether tracing is enabled for the current process. This is used to prevent tracing within
/// the Zygote process.
pub fn atrace_set_tracing_enabled(enabled: bool) {
    // SAFETY: No pointers are transferred.
    unsafe {
        trace_bind::atrace_set_tracing_enabled(enabled);
    }
}

/// `atrace_init` readies the process for tracing by opening the trace_marker file.
/// Calling any trace function causes this to be run, so calling it is optional.
/// This can be explicitly run to avoid setup delay on first trace function.
pub fn atrace_init() {
    // SAFETY: Call with no arguments.
    unsafe {
        trace_bind::atrace_init();
    }
}

/// Returns enabled tags as a bitmask.
///
/// The tag mask is converted into an `AtraceTag`, keeping flags that do not correspond to a tag.
pub fn atrace_get_enabled_tags() -> AtraceTag {
    // SAFETY: Call with no arguments that returns a 64-bit int.
    unsafe { AtraceTag::from_bits_retain(trace_bind::atrace_get_enabled_tags()) }
}

/// Test if a given tag is currently enabled.
///
/// It can be used as a guard condition around more expensive trace calculations.
pub fn atrace_is_tag_enabled(tag: AtraceTag) -> bool {
    // SAFETY: No pointers are transferred.
    unsafe { trace_bind::atrace_is_tag_enabled_wrap(tag.bits()) != 0 }
}

/// Trace the beginning of a context. `name` is used to identify the context.
///
/// This is often used to time function execution.
pub fn atrace_begin(tag: AtraceTag, name: &str) {
    if !atrace_is_tag_enabled(tag) {
        return;
    }

    let name_cstr = CString::new(name.as_bytes()).expect("CString::new failed");
    // SAFETY: The function does not accept the pointer ownership, only reads its contents.
    // The passed string is guaranteed to be null-terminated by CString.
    unsafe {
        trace_bind::atrace_begin_wrap(tag.bits(), name_cstr.as_ptr());
    }
}

/// Trace the end of a context.
///
/// This should match up (and occur after) a corresponding `atrace_begin`.
pub fn atrace_end(tag: AtraceTag) {
    // SAFETY: No pointers are transferred.
    unsafe {
        trace_bind::atrace_end_wrap(tag.bits());
    }
}

/// Trace the beginning of an asynchronous event. Unlike `atrace_begin`/`atrace_end` contexts,
/// asynchronous events do not need to be nested.
///
/// The name describes the event, and the cookie provides a unique identifier for distinguishing
/// simultaneous events.
///
/// The name and cookie used to begin an event must be used to end it.
pub fn atrace_async_begin(tag: AtraceTag, name: &str, cookie: i32) {
    if !atrace_is_tag_enabled(tag) {
        return;
    }

    let name_cstr = CString::new(name.as_bytes()).expect("CString::new failed");
    // SAFETY: The function does not accept the pointer ownership, only reads its contents.
    // The passed string is guaranteed to be null-terminated by CString.
    unsafe {
        trace_bind::atrace_async_begin_wrap(tag.bits(), name_cstr.as_ptr(), cookie);
    }
}

/// Trace the end of an asynchronous event.
///
/// This should have a corresponding `atrace_async_begin`.
pub fn atrace_async_end(tag: AtraceTag, name: &str, cookie: i32) {
    if !atrace_is_tag_enabled(tag) {
        return;
    }

    let name_cstr = CString::new(name.as_bytes()).expect("CString::new failed");
    // SAFETY: The function does not accept the pointer ownership, only reads its contents.
    // The passed string is guaranteed to be null-terminated by CString.
    unsafe {
        trace_bind::atrace_async_end_wrap(tag.bits(), name_cstr.as_ptr(), cookie);
    }
}

/// Trace the beginning of an asynchronous event.
///
/// In addition to the name and a cookie as in `atrace_async_begin`/`atrace_async_end`, a track name
/// argument is provided, which is the name of the row where this async event should be recorded.
///
/// The track name and cookie used to begin an event must be used to end it.
///
/// The cookie here must be unique on the track_name level, not the name level.
pub fn atrace_async_for_track_begin(tag: AtraceTag, track_name: &str, name: &str, cookie: i32) {
    if !atrace_is_tag_enabled(tag) {
        return;
    }

    let name_cstr = CString::new(name.as_bytes()).expect("CString::new failed");
    let track_name_cstr = CString::new(track_name.as_bytes()).expect("CString::new failed");
    // SAFETY: The function does not accept the pointer ownership, only reads its contents.
    // The passed strings are guaranteed to be null-terminated by CString.
    unsafe {
        trace_bind::atrace_async_for_track_begin_wrap(
            tag.bits(),
            track_name_cstr.as_ptr(),
            name_cstr.as_ptr(),
            cookie,
        );
    }
}

/// Trace the end of an asynchronous event.
///
/// This should correspond to a previous `atrace_async_for_track_begin`.
pub fn atrace_async_for_track_end(tag: AtraceTag, track_name: &str, cookie: i32) {
    if !atrace_is_tag_enabled(tag) {
        return;
    }

    let track_name_cstr = CString::new(track_name.as_bytes()).expect("CString::new failed");
    // SAFETY: The function does not accept the pointer ownership, only reads its contents.
    // The passed string is guaranteed to be null-terminated by CString.
    unsafe {
        trace_bind::atrace_async_for_track_end_wrap(tag.bits(), track_name_cstr.as_ptr(), cookie);
    }
}

/// Trace an instantaneous context. `name` is used to identify the context.
///
/// An "instant" is an event with no defined duration. Visually is displayed like a single marker
/// in the timeline (rather than a span, in the case of begin/end events).
///
/// By default, instant events are added into a dedicated track that has the same name of the event.
/// Use `atrace_instant_for_track` to put different instant events into the same timeline track/row.
pub fn atrace_instant(tag: AtraceTag, name: &str) {
    if !atrace_is_tag_enabled(tag) {
        return;
    }

    let name_cstr = CString::new(name.as_bytes()).expect("CString::new failed");
    // SAFETY: The function does not accept the pointer ownership, only reads its contents.
    // The passed string is guaranteed to be null-terminated by CString.
    unsafe {
        trace_bind::atrace_instant_wrap(tag.bits(), name_cstr.as_ptr());
    }
}

/// Trace an instantaneous context. `name` is used to identify the context. `track_name` is the name
/// of the row where the event should be recorded.
///
/// An "instant" is an event with no defined duration. Visually is displayed like a single marker
/// in the timeline (rather than a span, in the case of begin/end events).
pub fn atrace_instant_for_track(tag: AtraceTag, track_name: &str, name: &str) {
    if !atrace_is_tag_enabled(tag) {
        return;
    }

    let name_cstr = CString::new(name.as_bytes()).expect("CString::new failed");
    let track_name_cstr = CString::new(track_name.as_bytes()).expect("CString::new failed");
    // SAFETY: The function does not accept the pointer ownership, only reads its contents.
    // The passed string is guaranteed to be null-terminated by CString.
    unsafe {
        trace_bind::atrace_instant_for_track_wrap(
            tag.bits(),
            track_name_cstr.as_ptr(),
            name_cstr.as_ptr(),
        );
    }
}

/// Traces an integer counter value. `name` is used to identify the counter.
///
/// This can be used to track how a value changes over time.
pub fn atrace_int(tag: AtraceTag, name: &str, value: i32) {
    if !atrace_is_tag_enabled(tag) {
        return;
    }

    let name_cstr = CString::new(name.as_bytes()).expect("CString::new failed");
    // SAFETY: The function does not accept the pointer ownership, only reads its contents.
    // The passed string is guaranteed to be null-terminated by CString.
    unsafe {
        trace_bind::atrace_int_wrap(tag.bits(), name_cstr.as_ptr(), value);
    }
}

/// Traces a 64-bit integer counter value. `name` is used to identify the counter.
///
/// This can be used to track how a value changes over time.
pub fn atrace_int64(tag: AtraceTag, name: &str, value: i64) {
    if !atrace_is_tag_enabled(tag) {
        return;
    }

    let name_cstr = CString::new(name.as_bytes()).expect("CString::new failed");
    // SAFETY: The function does not accept the pointer ownership, only reads its contents.
    // The passed string is guaranteed to be null-terminated by CString.
    unsafe {
        trace_bind::atrace_int64_wrap(tag.bits(), name_cstr.as_ptr(), value);
    }
}

#[cfg(test)]
use self::tests::mock_atrace as trace_bind;

#[cfg(test)]
mod tests {
    use super::*;

    use std::ffi::CStr;
    use std::os::raw::c_char;

    /// Utilities to mock ATrace bindings.
    ///
    /// Normally, for behavior-driven testing we focus on the outcomes of the functions rather than
    /// calls into bindings. However, since the purpose of the library is to forward data into
    /// the underlying implementation (which we assume to be correct), that's what we test.
    pub mod mock_atrace {
        use std::cell::RefCell;
        use std::os::raw::c_char;

        /// Contains logic to check binding calls.
        /// Implement this trait in the test with mocking logic and checks in implemented functions.
        /// Default implementations panic.
        pub trait ATraceMocker {
            fn atrace_set_tracing_enabled(&mut self, _enabled: bool) {
                panic!("Unexpected call");
            }
            fn atrace_init(&mut self) {
                panic!("Unexpected call");
            }
            fn atrace_get_enabled_tags(&mut self) -> u64 {
                panic!("Unexpected call");
            }
            fn atrace_is_tag_enabled_wrap(&mut self, _tag: u64) -> u64 {
                panic!("Unexpected call");
            }
            fn atrace_begin_wrap(&mut self, _tag: u64, _name: *const c_char) {
                panic!("Unexpected call");
            }
            fn atrace_end_wrap(&mut self, _tag: u64) {
                panic!("Unexpected call");
            }
            fn atrace_async_begin_wrap(&mut self, _tag: u64, _name: *const c_char, _cookie: i32) {
                panic!("Unexpected call");
            }
            fn atrace_async_end_wrap(&mut self, _tag: u64, _name: *const c_char, _cookie: i32) {
                panic!("Unexpected call");
            }
            fn atrace_async_for_track_begin_wrap(
                &mut self,
                _tag: u64,
                _track_name: *const c_char,
                _name: *const c_char,
                _cookie: i32,
            ) {
                panic!("Unexpected call");
            }
            fn atrace_async_for_track_end_wrap(
                &mut self,
                _tag: u64,
                _track_name: *const c_char,
                _cookie: i32,
            ) {
                panic!("Unexpected call");
            }
            fn atrace_instant_wrap(&mut self, _tag: u64, _name: *const c_char) {
                panic!("Unexpected call");
            }
            fn atrace_instant_for_track_wrap(
                &mut self,
                _tag: u64,
                _track_name: *const c_char,
                _name: *const c_char,
            ) {
                panic!("Unexpected call");
            }
            fn atrace_int_wrap(&mut self, _tag: u64, _name: *const c_char, _value: i32) {
                panic!("Unexpected call");
            }
            fn atrace_int64_wrap(&mut self, _tag: u64, _name: *const c_char, _value: i64) {
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
        /// with_mocker(|mocker| mocker.atrace_begin_wrap(tag, name))
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
        // The functions are marked as unsafe to match the binding interface, won't compile otherwise.
        // The mocker methods themselves are not marked as unsafe.

        pub unsafe fn atrace_set_tracing_enabled(enabled: bool) {
            with_mocker(|m| m.atrace_set_tracing_enabled(enabled))
        }
        pub unsafe fn atrace_init() {
            with_mocker(|m| m.atrace_init())
        }
        pub unsafe fn atrace_get_enabled_tags() -> u64 {
            with_mocker(|m| m.atrace_get_enabled_tags())
        }
        pub unsafe fn atrace_is_tag_enabled_wrap(tag: u64) -> u64 {
            with_mocker(|m| m.atrace_is_tag_enabled_wrap(tag))
        }
        pub unsafe fn atrace_begin_wrap(tag: u64, name: *const c_char) {
            with_mocker(|m| m.atrace_begin_wrap(tag, name))
        }
        pub unsafe fn atrace_end_wrap(tag: u64) {
            with_mocker(|m| m.atrace_end_wrap(tag))
        }
        pub unsafe fn atrace_async_begin_wrap(tag: u64, name: *const c_char, cookie: i32) {
            with_mocker(|m| m.atrace_async_begin_wrap(tag, name, cookie))
        }
        pub unsafe fn atrace_async_end_wrap(tag: u64, name: *const c_char, cookie: i32) {
            with_mocker(|m| m.atrace_async_end_wrap(tag, name, cookie))
        }
        pub unsafe fn atrace_async_for_track_begin_wrap(
            tag: u64,
            track_name: *const c_char,
            name: *const c_char,
            cookie: i32,
        ) {
            with_mocker(|m| m.atrace_async_for_track_begin_wrap(tag, track_name, name, cookie))
        }
        pub unsafe fn atrace_async_for_track_end_wrap(
            tag: u64,
            track_name: *const c_char,
            cookie: i32,
        ) {
            with_mocker(|m| m.atrace_async_for_track_end_wrap(tag, track_name, cookie))
        }
        pub unsafe fn atrace_instant_wrap(tag: u64, name: *const c_char) {
            with_mocker(|m| m.atrace_instant_wrap(tag, name))
        }
        pub unsafe fn atrace_instant_for_track_wrap(
            tag: u64,
            track_name: *const c_char,
            name: *const c_char,
        ) {
            with_mocker(|m| m.atrace_instant_for_track_wrap(tag, track_name, name))
        }
        pub unsafe fn atrace_int_wrap(tag: u64, name: *const c_char, value: i32) {
            with_mocker(|m| m.atrace_int_wrap(tag, name, value))
        }
        pub unsafe fn atrace_int64_wrap(tag: u64, name: *const c_char, value: i64) {
            with_mocker(|m| m.atrace_int64_wrap(tag, name, value))
        }
    }

    #[test]
    fn forwards_set_tracing_enabled() {
        #[derive(Default)]
        struct CallCheck {
            set_tracing_enabled_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_set_tracing_enabled(&mut self, enabled: bool) {
                self.set_tracing_enabled_count += 1;
                assert!(self.set_tracing_enabled_count < 2);
                assert!(enabled);
            }

            fn finish(&self) {
                assert_eq!(self.set_tracing_enabled_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        atrace_set_tracing_enabled(true);

        mock_atrace::mocker_finish();
    }

    #[test]
    fn forwards_atrace_init() {
        #[derive(Default)]
        struct CallCheck {
            init_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_init(&mut self) {
                self.init_count += 1;
                assert!(self.init_count < 2);
            }

            fn finish(&self) {
                assert_eq!(self.init_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        atrace_init();

        mock_atrace::mocker_finish();
    }

    #[test]
    fn forwards_atrace_get_enabled_tags() {
        #[derive(Default)]
        struct CallCheck {
            get_enabled_tags_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_get_enabled_tags(&mut self) -> u64 {
                self.get_enabled_tags_count += 1;
                assert!(self.get_enabled_tags_count < 2);
                (cutils_trace_bindgen::ATRACE_TAG_HAL | cutils_trace_bindgen::ATRACE_TAG_GRAPHICS)
                    as u64
            }

            fn finish(&self) {
                assert_eq!(self.get_enabled_tags_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        let res = atrace_get_enabled_tags();
        assert_eq!(res, AtraceTag::Hal | AtraceTag::Graphics);

        mock_atrace::mocker_finish();
    }

    #[test]
    fn forwards_trace_begin() {
        #[derive(Default)]
        struct CallCheck {
            begin_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled_wrap(&mut self, _tag: u64) -> u64 {
                1
            }
            fn atrace_begin_wrap(&mut self, tag: u64, name: *const c_char) {
                self.begin_count += 1;
                assert!(self.begin_count < 2);
                assert_eq!(tag, cutils_trace_bindgen::ATRACE_TAG_APP as u64);
                // SAFETY: If the code under test is correct, the pointer is guaranteed to satisfy
                // the requirements of `CStr::from_ptr`. If the code is not correct, this section is
                // unsafe and will hopefully fail the test.
                unsafe {
                    assert_eq!(CStr::from_ptr(name).to_str().expect("to_str failed"), "Test Name");
                }
            }

            fn finish(&self) {
                assert_eq!(self.begin_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        atrace_begin(AtraceTag::App, "Test Name");

        mock_atrace::mocker_finish();
    }

    #[test]
    fn trace_begin_not_called_with_disabled_tag() {
        #[derive(Default)]
        struct CallCheck {
            is_tag_enabled_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled_wrap(&mut self, _tag: u64) -> u64 {
                self.is_tag_enabled_count += 1;
                assert!(self.is_tag_enabled_count < 2);
                0
            }
            fn atrace_begin_wrap(&mut self, _tag: u64, _name: *const c_char) {
                panic!("Begin should not be called with disabled tag.")
            }

            fn finish(&self) {
                assert_eq!(self.is_tag_enabled_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        atrace_begin(AtraceTag::App, "Ignore me");

        mock_atrace::mocker_finish();
    }

    #[test]
    fn forwards_trace_end() {
        #[derive(Default)]
        struct CallCheck {
            end_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_end_wrap(&mut self, tag: u64) {
                self.end_count += 1;
                assert!(self.end_count < 2);
                assert_eq!(tag, cutils_trace_bindgen::ATRACE_TAG_APP as u64);
            }

            fn finish(&self) {
                assert_eq!(self.end_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        atrace_end(AtraceTag::App);

        mock_atrace::mocker_finish();
    }

    #[test]
    fn can_combine_tags() {
        #[derive(Default)]
        struct CallCheck {
            begin_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled_wrap(&mut self, _tag: u64) -> u64 {
                1
            }
            fn atrace_begin_wrap(&mut self, tag: u64, _name: *const c_char) {
                self.begin_count += 1;
                assert!(self.begin_count < 2);
                assert_eq!(
                    tag,
                    (cutils_trace_bindgen::ATRACE_TAG_HAL | cutils_trace_bindgen::ATRACE_TAG_CAMERA)
                        as u64
                );
            }

            fn finish(&self) {
                assert_eq!(self.begin_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        atrace_begin(AtraceTag::Hal | AtraceTag::Camera, "foo");

        mock_atrace::mocker_finish();
    }

    #[test]
    fn forwards_is_tag_enabled() {
        #[derive(Default)]
        struct CallCheck {
            is_tag_enabled_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled_wrap(&mut self, tag: u64) -> u64 {
                self.is_tag_enabled_count += 1;
                assert!(self.is_tag_enabled_count < 2);
                assert_eq!(tag, cutils_trace_bindgen::ATRACE_TAG_ADB as u64);
                1
            }

            fn finish(&self) {
                assert_eq!(self.is_tag_enabled_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        let res = atrace_is_tag_enabled(AtraceTag::Adb);
        assert!(res);

        mock_atrace::mocker_finish();
    }

    #[test]
    fn forwards_async_begin() {
        #[derive(Default)]
        struct CallCheck {
            async_begin_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled_wrap(&mut self, _tag: u64) -> u64 {
                1
            }
            fn atrace_async_begin_wrap(&mut self, tag: u64, name: *const c_char, cookie: i32) {
                self.async_begin_count += 1;
                assert!(self.async_begin_count < 2);
                assert_eq!(tag, cutils_trace_bindgen::ATRACE_TAG_APP as u64);
                // SAFETY: If the code under test is correct, the pointer is guaranteed to satisfy
                // the requirements of `CStr::from_ptr`. If the code is not correct, this section is
                // unsafe and will hopefully fail the test.
                unsafe {
                    assert_eq!(CStr::from_ptr(name).to_str().expect("to_str failed"), "Test Name");
                }
                assert_eq!(cookie, 123);
            }

            fn finish(&self) {
                assert_eq!(self.async_begin_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        atrace_async_begin(AtraceTag::App, "Test Name", 123);

        mock_atrace::mocker_finish();
    }

    #[test]
    fn forwards_async_end() {
        #[derive(Default)]
        struct CallCheck {
            async_end_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled_wrap(&mut self, _tag: u64) -> u64 {
                1
            }
            fn atrace_async_end_wrap(&mut self, tag: u64, name: *const c_char, cookie: i32) {
                self.async_end_count += 1;
                assert!(self.async_end_count < 2);
                assert_eq!(tag, cutils_trace_bindgen::ATRACE_TAG_APP as u64);
                // SAFETY: If the code under test is correct, the pointer is guaranteed to satisfy
                // the requirements of `CStr::from_ptr`. If the code is not correct, this section is
                // unsafe and will hopefully fail the test.
                unsafe {
                    assert_eq!(CStr::from_ptr(name).to_str().expect("to_str failed"), "Test Name");
                }
                assert_eq!(cookie, 123);
            }

            fn finish(&self) {
                assert_eq!(self.async_end_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        atrace_async_end(AtraceTag::App, "Test Name", 123);

        mock_atrace::mocker_finish();
    }

    #[test]
    fn forwards_async_for_track_begin() {
        #[derive(Default)]
        struct CallCheck {
            async_for_track_begin_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled_wrap(&mut self, _tag: u64) -> u64 {
                1
            }
            fn atrace_async_for_track_begin_wrap(
                &mut self,
                tag: u64,
                track_name: *const c_char,
                name: *const c_char,
                cookie: i32,
            ) {
                self.async_for_track_begin_count += 1;
                assert!(self.async_for_track_begin_count < 2);
                assert_eq!(tag, cutils_trace_bindgen::ATRACE_TAG_APP as u64);
                // SAFETY: If the code under test is correct, the pointer is guaranteed to satisfy
                // the requirements of `CStr::from_ptr`. If the code is not correct, this section is
                // unsafe and will hopefully fail the test.
                unsafe {
                    assert_eq!(
                        CStr::from_ptr(track_name).to_str().expect("to_str failed"),
                        "Track"
                    );
                    assert_eq!(CStr::from_ptr(name).to_str().expect("to_str failed"), "Test Name");
                }
                assert_eq!(cookie, 123);
            }

            fn finish(&self) {
                assert_eq!(self.async_for_track_begin_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        atrace_async_for_track_begin(AtraceTag::App, "Track", "Test Name", 123);

        mock_atrace::mocker_finish();
    }

    #[test]
    fn forwards_async_for_track_end() {
        #[derive(Default)]
        struct CallCheck {
            async_for_track_end_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled_wrap(&mut self, _tag: u64) -> u64 {
                1
            }
            fn atrace_async_for_track_end_wrap(
                &mut self,
                tag: u64,
                track_name: *const c_char,
                cookie: i32,
            ) {
                self.async_for_track_end_count += 1;
                assert!(self.async_for_track_end_count < 2);
                assert_eq!(tag, cutils_trace_bindgen::ATRACE_TAG_APP as u64);
                // SAFETY: If the code under test is correct, the pointer is guaranteed to satisfy
                // the requirements of `CStr::from_ptr`. If the code is not correct, this section is
                // unsafe and will hopefully fail the test.
                unsafe {
                    assert_eq!(
                        CStr::from_ptr(track_name).to_str().expect("to_str failed"),
                        "Track"
                    );
                }
                assert_eq!(cookie, 123);
            }

            fn finish(&self) {
                assert_eq!(self.async_for_track_end_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        atrace_async_for_track_end(AtraceTag::App, "Track", 123);

        mock_atrace::mocker_finish();
    }

    #[test]
    fn forwards_trace_instant() {
        #[derive(Default)]
        struct CallCheck {
            trace_instant_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled_wrap(&mut self, _tag: u64) -> u64 {
                1
            }
            fn atrace_instant_wrap(&mut self, tag: u64, name: *const c_char) {
                self.trace_instant_count += 1;
                assert!(self.trace_instant_count < 2);
                assert_eq!(tag, cutils_trace_bindgen::ATRACE_TAG_APP as u64);
                // SAFETY: If the code under test is correct, the pointer is guaranteed to satisfy
                // the requirements of `CStr::from_ptr`. If the code is not correct, this section is
                // unsafe and will hopefully fail the test.
                unsafe {
                    assert_eq!(CStr::from_ptr(name).to_str().expect("to_str failed"), "Test Name");
                }
            }

            fn finish(&self) {
                assert_eq!(self.trace_instant_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        atrace_instant(AtraceTag::App, "Test Name");

        mock_atrace::mocker_finish();
    }

    #[test]
    fn forwards_trace_instant_for_track() {
        #[derive(Default)]
        struct CallCheck {
            trace_instant_for_track_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled_wrap(&mut self, _tag: u64) -> u64 {
                1
            }
            fn atrace_instant_for_track_wrap(
                &mut self,
                tag: u64,
                track_name: *const c_char,
                name: *const c_char,
            ) {
                self.trace_instant_for_track_count += 1;
                assert!(self.trace_instant_for_track_count < 2);
                assert_eq!(tag, cutils_trace_bindgen::ATRACE_TAG_APP as u64);
                // SAFETY: If the code under test is correct, the pointer is guaranteed to satisfy
                // the requirements of `CStr::from_ptr`. If the code is not correct, this section is
                // unsafe and will hopefully fail the test.
                unsafe {
                    assert_eq!(
                        CStr::from_ptr(track_name).to_str().expect("to_str failed"),
                        "Track"
                    );
                    assert_eq!(CStr::from_ptr(name).to_str().expect("to_str failed"), "Test Name");
                }
            }

            fn finish(&self) {
                assert_eq!(self.trace_instant_for_track_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        atrace_instant_for_track(AtraceTag::App, "Track", "Test Name");

        mock_atrace::mocker_finish();
    }

    #[test]
    fn forwards_trace_int() {
        #[derive(Default)]
        struct CallCheck {
            trace_int_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled_wrap(&mut self, _tag: u64) -> u64 {
                1
            }
            fn atrace_int_wrap(&mut self, tag: u64, name: *const c_char, value: i32) {
                self.trace_int_count += 1;
                assert!(self.trace_int_count < 2);
                assert_eq!(tag, cutils_trace_bindgen::ATRACE_TAG_APP as u64);
                // SAFETY: If the code under test is correct, the pointer is guaranteed to satisfy
                // the requirements of `CStr::from_ptr`. If the code is not correct, this section is
                // unsafe and will hopefully fail the test.
                unsafe {
                    assert_eq!(CStr::from_ptr(name).to_str().expect("to_str failed"), "Test Name");
                }
                assert_eq!(value, 32);
            }

            fn finish(&self) {
                assert_eq!(self.trace_int_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        atrace_int(AtraceTag::App, "Test Name", 32);

        mock_atrace::mocker_finish();
    }

    #[test]
    fn forwards_trace_int64() {
        #[derive(Default)]
        struct CallCheck {
            trace_int64_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled_wrap(&mut self, _tag: u64) -> u64 {
                1
            }
            fn atrace_int64_wrap(&mut self, tag: u64, name: *const c_char, value: i64) {
                self.trace_int64_count += 1;
                assert!(self.trace_int64_count < 2);
                assert_eq!(tag, cutils_trace_bindgen::ATRACE_TAG_APP as u64);
                // SAFETY: If the code under test is correct, the pointer is guaranteed to satisfy
                // the requirements of `CStr::from_ptr`. If the code is not correct, this section is
                // unsafe and will hopefully fail the test.
                unsafe {
                    assert_eq!(CStr::from_ptr(name).to_str().expect("to_str failed"), "Test Name");
                }
                assert_eq!(value, 64);
            }

            fn finish(&self) {
                assert_eq!(self.trace_int64_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        atrace_int64(AtraceTag::App, "Test Name", 64);

        mock_atrace::mocker_finish();
    }

    #[test]
    fn scoped_event_starts_and_ends_in_order() {
        #[derive(Default)]
        struct CallCheck {
            begin_count: u32,
            end_count: u32,
            instant_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled_wrap(&mut self, _tag: u64) -> u64 {
                1
            }

            fn atrace_begin_wrap(&mut self, tag: u64, name: *const c_char) {
                assert_eq!(self.end_count, 0);
                assert_eq!(self.instant_count, 0);

                self.begin_count += 1;
                assert!(self.begin_count < 2);
                assert_eq!(tag, cutils_trace_bindgen::ATRACE_TAG_APP as u64);
                // SAFETY: If the code under test is correct, the pointer is guaranteed to satisfy
                // the requirements of `CStr::from_ptr`. If the code is not correct, this section is
                // unsafe and will hopefully fail the test.
                unsafe {
                    assert_eq!(
                        CStr::from_ptr(name).to_str().expect("to_str failed"),
                        "Scoped Event"
                    );
                }
            }

            fn atrace_instant_wrap(&mut self, _tag: u64, _name: *const c_char) {
                // We don't care about the contents of the event, we only use it to check begin/end ordering.
                assert_eq!(self.begin_count, 1);
                assert_eq!(self.end_count, 0);

                self.instant_count += 1;
                assert!(self.instant_count < 2);
            }

            fn atrace_end_wrap(&mut self, tag: u64) {
                assert_eq!(self.begin_count, 1);
                assert_eq!(self.instant_count, 1);

                self.end_count += 1;
                assert!(self.end_count < 2);
                assert_eq!(tag, cutils_trace_bindgen::ATRACE_TAG_APP as u64);
            }

            fn finish(&self) {
                assert_eq!(self.begin_count, 1);
                assert_eq!(self.end_count, 1);
                assert_eq!(self.instant_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        {
            let _event_guard = begin_scoped_event(AtraceTag::App, "Scoped Event");
            atrace_instant(AtraceTag::App, "Instant event called within scoped event");
        }

        mock_atrace::mocker_finish();
    }

    // Need to have this alias to make the macro work, since it calls atrace::begin_scoped_event.
    use crate as atrace;
    fn traced_method_for_test() {
        trace_method!(AtraceTag::App);
        atrace_instant(AtraceTag::App, "Instant event called within method");
    }

    #[test]
    fn method_trace_starts_and_ends_in_order() {
        #[derive(Default)]
        struct CallCheck {
            begin_count: u32,
            end_count: u32,
            instant_count: u32,
        }

        impl mock_atrace::ATraceMocker for CallCheck {
            fn atrace_is_tag_enabled_wrap(&mut self, _tag: u64) -> u64 {
                1
            }

            fn atrace_begin_wrap(&mut self, tag: u64, name: *const c_char) {
                assert_eq!(self.end_count, 0);
                assert_eq!(self.instant_count, 0);

                self.begin_count += 1;
                assert!(self.begin_count < 2);
                assert_eq!(tag, cutils_trace_bindgen::ATRACE_TAG_APP as u64);
                // SAFETY: If the code under test is correct, the pointer is guaranteed to satisfy
                // the requirements of `CStr::from_ptr`. If the code is not correct, this section is
                // unsafe and will hopefully fail the test.
                unsafe {
                    assert_eq!(
                        CStr::from_ptr(name).to_str().expect("to_str failed"),
                        "lib::tests::traced_method_for_test"
                    );
                }
            }

            fn atrace_instant_wrap(&mut self, _tag: u64, _name: *const c_char) {
                // We don't care about the contents of the event, we only use it to check begin/end ordering.
                assert_eq!(self.begin_count, 1);
                assert_eq!(self.end_count, 0);

                self.instant_count += 1;
                assert!(self.instant_count < 2);
            }

            fn atrace_end_wrap(&mut self, tag: u64) {
                assert_eq!(self.begin_count, 1);
                assert_eq!(self.instant_count, 1);

                self.end_count += 1;
                assert!(self.end_count < 2);
                assert_eq!(tag, cutils_trace_bindgen::ATRACE_TAG_APP as u64);
            }

            fn finish(&self) {
                assert_eq!(self.begin_count, 1);
                assert_eq!(self.end_count, 1);
                assert_eq!(self.instant_count, 1);
            }
        }

        let _guard = mock_atrace::set_scoped_mocker(CallCheck::default());

        traced_method_for_test();

        mock_atrace::mocker_finish();
    }
}
