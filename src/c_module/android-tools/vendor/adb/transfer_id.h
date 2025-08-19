/*
 * Copyright (C) 2021 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#pragma once

#include <stddef.h>
#include <stdint.h>

enum class TransferDirection : uint64_t {
    READ = 0,
    WRITE = 1,
};

struct TransferId {
    TransferDirection direction : 1;
    uint64_t id : 63;

    constexpr TransferId() : TransferId(TransferDirection::READ, 0) {}
    TransferId(const TransferId& copy) = default;
    TransferId(TransferId&& move) = default;

    TransferId& operator=(const TransferId& copy) = default;
    TransferId& operator=(TransferId&& move) = default;

  private:
    constexpr TransferId(TransferDirection direction, uint64_t id) : direction(direction), id(id) {}

  public:
    bool operator==(const TransferId& rhs) const {
        return static_cast<uint64_t>(*this) == static_cast<uint64_t>(rhs);
    }

    constexpr explicit operator uint64_t() const {
        return static_cast<uint64_t>(direction) << 63 | id;
    }

    static constexpr TransferId read(uint64_t id) {
        return TransferId(TransferDirection::READ, id);
    }

    static constexpr TransferId write(uint64_t id) {
        return TransferId(TransferDirection::WRITE, id);
    }

    static constexpr TransferId from_value(uint64_t value) {
        uint64_t mask = static_cast<uint64_t>(1) << 63;

        TransferId result;
        result.direction = static_cast<TransferDirection>(!!(value & mask));
        result.id = value & (mask - 1);
        return result;
    }
};

namespace std {
template <>
struct hash<TransferId> {
    size_t operator()(TransferId id) const { return hash<uint64_t>()(static_cast<uint64_t>(id)); }
};
}  // namespace std
