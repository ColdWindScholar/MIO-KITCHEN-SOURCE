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
