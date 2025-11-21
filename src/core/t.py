from core.squashfs import SuperBlock, Compressor

if __name__ == "__main__":
    with open(
            r"C:\Users\16612\PycharmProjects\MIO-KITCHEN-SOURCE\T1C1.6T_703000731AA&703000617AA _02.02.00_6279\T1C火星大火星-6279\chery_update\9la_t1cm_update_dmc_703000617AA_006279-006279.zip",
            "rb") as f:
        ss = SuperBlock()
        data = f.read(len(ss))
        ss.unpack(data)
        print(Compressor(ss.compressor).name)
        print(ss.inode_count)
        print(ss.mod_time)
        print(ss.block_size)
        print(ss.frag_count)
        print(ss.block_size / 2 == ss.block_log)