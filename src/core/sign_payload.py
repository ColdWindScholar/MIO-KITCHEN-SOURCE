# Copyright (C) 2022-2025 The MIO-KITCHEN-SOURCE Project
#
# Licensed under theGNU AFFERO GENERAL PUBLIC LICENSE, Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html#license-text
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, utils
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_der_private_key, Encoding, PrivateFormat, NoEncryption


def payload_sign(inkey, in_, out):
    with open(inkey, 'rb') as fkey, open(in_, 'rb') as fin_, open(out, 'wb') as fout:
        signature = load_pem_private_key(fkey.read(), password=None).sign(
            fin_.read(),
            padding.PKCS1v15(),
            utils.Prehashed(hashes.SHA256())
        )
        fout.write(signature)

def private_der_to_pem(inkey, outkey, password=None):
    with open(inkey, 'rb') as f, open(outkey, 'wb') as o:
        key = load_der_private_key(f.read(), password=password)
        o.write(key.private_bytes(encoding=Encoding.PEM, format=PrivateFormat.PKCS8, encryption_algorithm=NoEncryption()))
