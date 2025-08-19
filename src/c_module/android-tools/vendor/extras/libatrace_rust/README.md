# libatrace_rust - ATrace bindings for Rust

Wrapper library for ATrace methods from libcutils.

## Quick start

### Using ATrace bindings directly

Add the library to your `rustlibs` in `Android.bp`:

```text
rustlibs: [
    ...
    "libatrace_rust",
    ...
],
```

Call tracing methods:

```rust
fn important_function() {
    // Use this macro to trace a function.
    atrace::trace_method!(AtraceTag::App);

    if condition {
        // Use a scoped event to trace inside a scope.
        let _event = atrace::begin_scoped_event(AtraceTag::App, "Inside a scope");
        ...
    }

    // Or just use the wrapped API directly.
    atrace::atrace_begin(AtraceTag::App, "My event");
    ...
    atrace::atrace_end(AtraceTag::App)
}
```

See more in the [example](./example/src/main.rs).

You're all set! Now you can collect a trace with your favorite tracing tool like
[Perfetto](https://perfetto.dev/docs/data-sources/atrace).

### Using the tracing crate

You can use the ATrace layer for the [tracing](https://docs.rs/tracing/latest/tracing/) crate.
Compared to using the bindings directly, it has better instrumentation points and customizability.
The main drawback is lower performance. See the [Performance](#performance) section below for more
information.

Add the tracing libraries to your `rustlibs` in `Android.bp`:

```text
    rustlibs: [
        ...
        "libatrace_tracing_subscriber",
        "libtracing_subscriber",
        "libtracing",
        ...
    ],
```

[Initialize](https://docs.rs/tracing/latest/tracing/index.html#in-executables) the subscriber
before calling the tracing methods, usually somewhere in the beginning of `main()`.

```rust
// Initialize the subscriber, panic if it fails.
tracing_subscriber::registry()
        .with(AtraceSubscriber::default().with_filter())
        .init();
```

The subscriber defaults to `AtraceTag::App`. Use other tags by creating the subscriber with
`AtraceSubscriber::new(tag: AtraceTag)`.

You can combine the subscriber with other
[layers](https://docs.rs/tracing-subscriber/latest/tracing_subscriber/layer/index.html). In
that case, omit `with_filter()` from the `AtraceSubscriber` initialization - it is an optimization
that disables instrumentation points when ATrace is disabled and it would affect other layers as
well.

Now you can
[record spans and events](https://docs.rs/tracing/latest/tracing/index.html#recording-spans-and-events):

```rust
// This macro would automatically create and enter a span with function name and arguments.
#[tracing::instrument]
fn important_function() {
    if condition {
        // Use span! to trace inside a scope.
        let _entered = tracing::span!(tracing::Level::TRACE, "Inside a scope").entered();
        ...
    }

    // Use event! to record an instant event.
    // You can annotate spans and events with fields. They will be appended to the end of
    // the Atrace event.
    tracing::info!(field="value", "My event");
}
```

See more in the [example](./example/src/tracing_subscriber_sample.rs) and check out the docs for
the [tracing](https://docs.rs/tracing/latest/tracing/index.html) and
[tracing-subscriber](https://docs.rs/tracing-subscriber/latest/tracing_subscriber/index.html)
crates.

## Performance

This section is an overview, you can find specific numbers in
[benchmark/README.md](./benchmark/README.md).

### ATrace bindings

When tracing is enabled, you can expect 1-10 us per event - this is a significant cost that may
affect the performance of hot high-frequency methods. When the events are disabled, calling them is
cheap - on the order of 5-10 ns. There is a 10-20% overhead from the wrapper, mostly caused by
string conversion when tracing is enabled.

### Tracing subscriber

The subscriber uses the bindings and adds its own overhead that depends on usage:

* With tracing disabled and subscriber created `with_filter`, events cost around 30 ns. Not using
  the filter brings the cost up to 100-400 ns per event.
* Instant events (`event!`) add roughly 200 ns to the bindings - 1.5 vs 1.3 us.
* Spans (`span!`) are roughly 400 ns slower - 2.8 vs 2.4 us.
* Using [fields](https://docs.rs/tracing/latest/tracing/index.html#recording-fields) adds time
  that depends on the amount of the fields and the cost of converting them to strings. Typically
  it is around an extra 500 ns per event and an extra 1 us for a span.
