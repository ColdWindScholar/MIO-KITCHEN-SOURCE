/*
 * Copyright (C) 2013 The Android Open Source Project
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

#define _GNU_SOURCE  /* needed for asprintf */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include <crypto_utils/android_pubkey.h>

#include <openssl/evp.h>
#include <openssl/objects.h>
#include <openssl/pem.h>
#include <openssl/rsa.h>
#include <openssl/sha.h>

static int write_public_keyfile(RSA *private_key, const char *private_key_path)
{
    uint8_t key_data[ANDROID_PUBKEY_ENCODED_SIZE];
    BIO *bfile = NULL;
    char *path = NULL;
    int ret = -1;

    if (asprintf(&path, "%s.pub", private_key_path) < 0)
        goto out;

    if (!android_pubkey_encode(private_key, key_data, sizeof(key_data)))
        goto out;

    bfile = BIO_new_file(path, "w");
    if (!bfile)
        goto out;

    BIO_write(bfile, key_data, sizeof(key_data));
    BIO_flush(bfile);

    ret = 0;
out:
    BIO_free_all(bfile);
    free(path);
    return ret;
}

static int convert_x509(const char *pem_file, const char *key_file)
{
    int ret = -1;
    FILE *f = NULL;
    EVP_PKEY *pkey = NULL;
    RSA *rsa = NULL;
    X509 *cert = NULL;

    if (!pem_file || !key_file) {
        goto out;
    }

    f = fopen(pem_file, "r");
    if (!f) {
        printf("Failed to open '%s'\n", pem_file);
        goto out;
    }

    cert = PEM_read_X509(f, &cert, NULL, NULL);
    if (!cert) {
        printf("Failed to read PEM certificate from file '%s'\n", pem_file);
        goto out;
    }

    pkey = X509_get_pubkey(cert);
    if (!pkey) {
        printf("Failed to extract public key from certificate '%s'\n", pem_file);
        goto out;
    }

    rsa = EVP_PKEY_get1_RSA(pkey);
    if (!rsa) {
        printf("Failed to get the RSA public key from '%s'\n", pem_file);
        goto out;
    }

    if (write_public_keyfile(rsa, key_file) < 0) {
        printf("Failed to write public key\n");
        goto out;
    }

    ret = 0;

out:
    if (f) {
        fclose(f);
    }
    if (cert) {
        X509_free(cert);
    }
    if (pkey) {
        EVP_PKEY_free(pkey);
    }
    if (rsa) {
        RSA_free(rsa);
    }

    return ret;
}

static int generate_key(const char *file)
{
    int ret = -1;
    FILE *f = NULL;
    RSA* rsa = RSA_new();
    BIGNUM* exponent = BN_new();
    EVP_PKEY* pkey = EVP_PKEY_new();

    if (!pkey || !exponent || !rsa) {
        printf("Failed to allocate key\n");
        goto out;
    }

    BN_set_word(exponent, RSA_F4);
    RSA_generate_key_ex(rsa, 2048, exponent, NULL);
    EVP_PKEY_set1_RSA(pkey, rsa);

    f = fopen(file, "w");
    if (!f) {
        printf("Failed to open '%s'\n", file);
        goto out;
    }

    if (!PEM_write_PrivateKey(f, pkey, NULL, NULL, 0, NULL, NULL)) {
        printf("Failed to write key\n");
        goto out;
    }

    if (write_public_keyfile(rsa, file) < 0) {
        printf("Failed to write public key\n");
        goto out;
    }

    ret = 0;

out:
    if (f)
        fclose(f);
    EVP_PKEY_free(pkey);
    RSA_free(rsa);
    BN_free(exponent);
    return ret;
}

static void usage(){
    printf("Usage: generate_verity_key <path-to-key> | -convert <path-to-x509-pem> <path-to-key>\n");
}

int main(int argc, char *argv[]) {
    if (argc == 2) {
        return generate_key(argv[1]);
    } else if (argc == 4 && !strcmp(argv[1], "-convert")) {
        return convert_x509(argv[2], argv[3]);
    } else {
        usage();
        exit(-1);
    }
}
