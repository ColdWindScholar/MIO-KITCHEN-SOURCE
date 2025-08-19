# `libjsonpbparse`

This library provides functions to parse a JSON file to a structured Protobuf
message.

At this time of writing, `libprotobuf-cpp-full` is at version 3.0.0-beta, and
unknown fields in a JSON file cannot be ignored. Do **NOT** use this library in
vendor / recovery until `libprotobuf-cpp-full` is updated.

## Using `libjsoncpp` in parser code

Since `libjsonpbparse` cannot be used in vendor / recovery processes yet,
`libjsoncpp` is used instead. However, there are notable differences in the
logic of `libjsoncpp` and `libprotobuf` when parsing JSON files.

- There are no implicit string to integer conversion in `libjsoncpp`. Hence:
  - If the Protobuf schema uses 64-bit integers (`(s|fixed|u|)int64`):
    - The JSON file must use strings (to pass tests in `libjsonpbverify`)
    - Parser code (that uses `libjsoncpp`) must explicitly convert strings to
      integers. Example:
      ```c++
      strtoull(value.asString(), 0, 10)
      ```
  - If the Protobuf schema uses special floating point values:
    - The JSON file must use strings (e.g. `"NaN"`, `"Infinity"`, `"-Infinity"`)
    - Parser code must explicitly handle these cases. Example:
      ```c++
      double d;
      if (value.isNumeric()) {
        d = value.asDouble();
      } else {
        auto&& s = value.asString();
        if (s == "NaN") d = std::numeric_limits<double>::quiet_NaN();
        else if (s == "Infinity") d = std::numeric_limits<double>::infinity();
        else if (s == "-Infinity") d = -std::numeric_limits<double>::infinity();
      }
      ```
- `libprotobuf` accepts either `lowerCamelCase` (or `json_name` option if it is
  defined) or the original field name as keys in the input JSON file.
  The test in `libjsonpbverify` explicitly check this case to avoid ambiguity;
  only the original field name (or `json_name` option if it is defined) can be
  used.

Once `libprotobuf` in the source tree is updated to a higher version and
`libjsonpbparse` is updated to ignore unknown fields in JSON files, all parsing
code must be converted to use `libjsonpbparse` for consistency.

# `libjsonpbverify`

This library provides functions and tests to examine a JSON file and validate
it against a Protobuf message definition.

In addition to a validity check that `libprotobuf` can convert the JSON file to a
Protobuf message (using `libjsonpbparse`), it also checks the following:

- Whether there are fields unknown to the schema. All fields in the JSON file
  must be well defined in the schema.
- Whether the Protobuf file defines JSON keys clearly. The JSON keys must be
  the `json_name` option of a Protobuf field, or name of a Protobuf field if
  `json_name` is not defined. `lowerCamelCase` supported by `libprotobuf` is
  explicitly disallowed (unless explicitly used in `json_name`). For example,
  in the following Protobuf file, only keys `foo_bar` and `barBaz` are allowed
  in the JSON file:
  ```
  message Foo {
      string foo_bar = 1;
      string bar_baz = 2 [json_name = "barBaz"];
  }
  ```
- Whether `json == convert_to_json(convert_to_pb(json))`, using `libprotobuf`.
  This imposes additional restrictions including:
  - Enum values must be present as names (not integer values) in the JSON file.
  - 64-bit integers and special floating point values (infinity, NaN) must
    always be strings.

## Defining a JSON schema using Protobuf

Check [JSON Mapping](https://developers.google.com/protocol-buffers/docs/proto3#json)
before defining a Protobuf object as a JSON schema. In general:

- **Use proto3**. `libjsonverify` does not support proto2.
- JSON booleans should be `bool`.
- JSON numbers should be `(s|fixed|u|)int32`, `float`, or `double` in the schema
- JSON strings are generally `string`s, but if you want to impose more
  restrictions on the string, you can also use `Timestamp`, `bytes`,
  **`float`** or **`double`** (if NaN and infinity are valid values),
  enumerations, etc.
  - If a custom enumeration is used, parser code should **NOT** error when the
    enumeration value name is unknown, as enumeration definitions may be
    extended in the future.
- JSON arrays should be repeated fields.
- JSON objects should be a well-defined `message`, unless you have a good reason
  to use `map<string, T>`.
- Don't use `Any`; it defeats the purpose of having the schema.

## Validating a JSON file against a Protobuf definition

Example:
```c++
#include <jsonpb/verify.h>
using namespace ::android::jsonpb;
std::unique_ptr<JsonSchemaTestConfig> CreateCgroupsParam() {

}
INSTANTIATE_TEST_SUITE_P(LibProcessgroupProto, JsonSchemaTest,
                         ::testing::Values(MakeTestParam<Cgroups>("cgroups.json")));
```
