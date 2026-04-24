#!/bin/python3

from src.core.splash_editor.src.logo_gen import GenerateLogoImg


def splash_repack(input_dir: str, output_file: str, nolimit=False):
    print("Using predefined DataSize to generate splash...")
    n = 1
    print("Generate 1024 byte of empty file...")
    with open(output_file, "wb") as f:
        f.write(b'\x00' * 1024)
    for i in [100864, 613888, 101888, 204288, 204288, 0]:
        if nolimit:
            i = 0
        print(f"Compress splash{n}.png padding into {output_file}...")
        data = GenerateLogoImg(f"{input_dir}/splash{n}.png", i)
        a = len(data)
        b = a + 512
        print(f"Data size: {a}\nPredefined:{i}")
        if i != 0:
            if a > b:
                print(f"Error of picture [pic/splash{n}.png]... Image is too complex...")
                print("Please replace it with a more sample picture...")
                return
        with open(output_file, "ab") as f:
            f.write(data)
        n += 1
    print("Done...")
