DDPH_MAGIC = 0x48504444
DDPH_HDR_OFFSET = 0x0
SPLASH_HDR_MAGIC = "SPLASH LOGO!"
SPLASH_HDR_OFFSET = 0x4000
SPLASH_HDR_METADATA_OFFSET = SPLASH_HDR_OFFSET + 12
SPLASH_HDR_METADATA_DONE_OFFSET = SPLASH_HDR_METADATA_OFFSET + (0x40 * 4)
SPLASH_METADATA_OFFSET = SPLASH_HDR_OFFSET + 0x120
SPLASH_METADATA_BLOCK = 0x80
DATA_OFFSET = 0x8000
class DataInfo:
    offset:int
    realsz:int
    compsz:int
    name:str
    def gen(self):
        buffer = bytearray(SPLASH_METADATA_BLOCK)
        view = memoryview(buffer)
"""
export class DataInfo {
    constructor(
        public offset: number,
        public realsz: number,
        public compsz: number,
        public name: string
    ) { };

    /**
     * Generate arraybuffer with datainfo
     *
     * @returns ArrayBuffer
     */
    public gen() {
        var buffer = new ArrayBuffer(SPLASH_METADATA_BLOCK);
        let view = new DataView(buffer);
        let encoder = new TextEncoder();
        let array = encoder.encode(this.name).fill(0, this.name.length, SPLASH_METADATA_BLOCK - 12);

        view.setUint32(0, this.offset, true);
        view.setUint32(4, this.realsz, true);
        view.setUint32(8, this.compsz, true);
        (new Uint8Array(buffer)).set(array, 12);

        return new Uint8Array(buffer);
    }
};

export class OPPOSPlashImage {
    /**
     *
     * Read OPPO Splash Image from ArrayBuffer OR Buffer
     *
     * @param data - ArrayBuffer or Buffer
     */
    constructor(data: any, verbose = false) {
        // 检查 data 是否是 ArrayBuffer 类型
        if (data instanceof ArrayBuffer) {
            this.data = data;
        } else if (Buffer.isBuffer(data)) {
            // 如果 data 是 Node.js 的 Buffer 类型，转换为 ArrayBuffer
            this.data = data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength);
        } else {
            throw new Error("Unsupported data type");
        }

        const view = new DataView(this.data); // 使用 const 进行声明

        const readDdph = () => {
            this.ddphMagic = view.getUint32(DDPH_HDR_OFFSET, true);
            this.ddphFlag = view.getUint32(DDPH_HDR_OFFSET + 4, true);

            if (this.ddphMagic = DDPH_MAGIC) {
                console.log("DDPH MAGIC FOUND!");
            }
        };

        const readSplash = () => {
            const decodeArrayBuffer = (data: ArrayBuffer) => {
                const array = (new Uint8Array(data)).filter((i) => i != 0);
                // remove 00 from array
                for (let a in array) {

                }
                const decoder = new TextDecoder('ascii');
                return decoder.decode(array);
            };

            this.splashMagic = this.data.slice(SPLASH_HDR_OFFSET, SPLASH_HDR_OFFSET + 12);
            if (decodeArrayBuffer(this.splashMagic) != SPLASH_HDR_MAGIC) {
                throw new Error("This seems not a OPPO Splash image!");
            };

            // Reset metadata
            this.metadata = [];
            this.metadataString = [];
            // Read metadata
            for (var i = 0; i < 4; i++) {
                this.metadata.push(this.data.slice(SPLASH_HDR_METADATA_OFFSET + (0x40 * i), SPLASH_HDR_METADATA_OFFSET + (0x40 * i) + 0x40));
                this.metadataString.push(decodeArrayBuffer(this.metadata[i]));
                console.log("Read metadata " + i + " with:", this.metadataString[i]);
            };

            // infos
            this.imageNum = view.getUint32(SPLASH_HDR_METADATA_DONE_OFFSET, true);
            this.version = view.getUint32(SPLASH_HDR_METADATA_DONE_OFFSET + 4, true);
            this.width = view.getUint32(SPLASH_HDR_METADATA_DONE_OFFSET + 8, true);
            this.height = view.getUint32(SPLASH_HDR_METADATA_DONE_OFFSET + 12, true);
            this.special = view.getUint32(SPLASH_HDR_METADATA_DONE_OFFSET + 16, true);

            if (verbose) {
                console.log("Read imageNum:", this.imageNum);
                console.log("Read version:", this.version);
                console.log("Read width:", this.width);
                console.log("Read height:", this.height);
                console.log("Read special flag:", this.special);
            };

            // Read data info
            var off = SPLASH_METADATA_OFFSET;
            this.dataInfos = [];
            for (var i = 0; i < this.imageNum; i++) {
                this.dataInfos.push(new DataInfo(
                    view.getUint32(off, true),
                    view.getUint32(off + 4, true),
                    view.getUint32(off + 8, true),
                    decodeArrayBuffer(view.buffer.slice(off + 12, off + 0x80))
                ));
                if (verbose) {
                    console.log("Read Metadata Info at:", off);
                    console.log("ReadInfo:")
                    console.log("offset:", this.dataInfos[i].offset);
                    console.log("realsz:", this.dataInfos[i].realsz);
                    console.log("compsz:", this.dataInfos[i].compsz);
                    console.log("name:", this.dataInfos[i].name);
                };
                off += SPLASH_METADATA_BLOCK;
            };

            // Save compressed data
            this.compData = [];
            for (let i = 0; i < this.imageNum; i++) {
                // 计算数据片段的开始和结束位置
                const start = DATA_OFFSET + this.dataInfos[i].offset;
                const end = start + this.dataInfos[i].compsz; // 结束位置是开始位置加上压缩数据的大小

                this.compData.push(
                    this.data.slice(start, end)
                );
                if (verbose) {
                    console.log(`Saved compressed data slice from offset ${start} to ${end}`);
                };
            }


            // Done
            console.log("Load OPPO Splash image successfully!");

        };

        readDdph();
        readSplash();
    }

    data: ArrayBuffer;
    ddphMagic!: number;
    ddphFlag!: number;

    splashMagic!: ArrayBuffer;
    metadata: ArrayBuffer[] = [];
    metadataString: string[] = [];
    imageNum!: number;
    version!: number;
    width!: number;
    height!: number;
    special!: number;

    dataInfos: DataInfo[] = [];

    compData: ArrayBuffer[] = [];

    public test() {
        // Check Data Size
        for (var i = 0; i < this.imageNum; i++) {
            if (this.compData[i].byteLength == this.dataInfos[i].compsz) {
                console.log("Check saved success at index:", i);
            } else {
                console.log("Check failed at index:", i, "data length:", this.compData[i].byteLength, "expect:", this.dataInfos[i].compsz);
            }
        };
        // Check Raw Size
        for (let i = 0; i < this.imageNum; i++) {
            let rawData = pako.ungzip(this.compData[i]);
            if (rawData.length == this.dataInfos[i].realsz) {
                console.log("Check decompress raw data size successful at index: ", i);
            } else {
                console.log("Check decompressed data size failed:", rawData.length, "!=", this.dataInfos[i].realsz)
            }
        };
    };

    private arrayBufferToBase64(buffer: ArrayBuffer): string {
        if (typeof window !== "undefined" && typeof window.btoa === "function") {
            // 浏览器环境
            const binary = String.fromCharCode(...new Uint8Array(buffer));
            return window.btoa(binary);
        } else if (typeof Buffer !== "undefined") {
            // Node.js 环境
            return Buffer.from(buffer).toString('base64');
        } else {
            throw new Error("Unsupported environment: Cannot convert ArrayBuffer to Base64.");
        }
    }

    /**
     * Get Image By Index, will return image ArrayBuffer
     *
     * @param index
     * @returns ArrayBuffer
     */
    public getImageByIndex(index: number) {
        return pako.ungzip(this.compData[index]);
    }

    public getImageB64ByIndex(index: number) {
        return this.arrayBufferToBase64(this.getImageByIndex(index));
    }

    /**
     * Get decompressed bmp preview image blob by index
     *
     * @return Blob
     */
    public getRawImageBlobByIndex(index: number) {
        return new Blob([this.getImageByIndex(index)], { type: 'image/bmp' });
    }

    /**
     * Generate new splash
     *
     * @returns image Blob
     */
    public genNewImage() {
        // calc splash image size
        let imgsize = DATA_OFFSET;
        for (let i = 0; i < this.imageNum; i++) {
            imgsize += this.compData[i].byteLength;
        }

        // Construct new arraybuffer
        let newArray = new ArrayBuffer(imgsize);
        let newView = new DataView(newArray);
        let oldView = new DataView(this.data);

        // wirte ddph
        if (this.ddphMagic = DDPH_MAGIC) {
            newView.setUint32(DDPH_HDR_OFFSET, this.ddphMagic, true);
            newView.setUint32(DDPH_HDR_OFFSET + 4, this.ddphFlag, true);
        }

        // write splash hdr
        for (let i = 0; i < SPLASH_HDR_MAGIC.length; i++) {
            newView.setUint8(SPLASH_HDR_OFFSET + i,
                oldView.getUint8(SPLASH_HDR_OFFSET + i));
        }
        // write hdr metadatas
        for (let i = 0; i < 4; i++) {
            let view = new Uint8Array(newView.buffer);
            let view2 = new Uint8Array(oldView.buffer);

            view.set(view2.subarray(SPLASH_HDR_METADATA_OFFSET + (0x40 * i), SPLASH_HDR_METADATA_OFFSET + (0x40 * i) + 0x40), SPLASH_HDR_METADATA_OFFSET + (0x40 * i));
        }
        // write else hdr data
        newView.setUint32(SPLASH_HDR_METADATA_DONE_OFFSET, this.imageNum, true);
        newView.setUint32(SPLASH_HDR_METADATA_DONE_OFFSET + 4, this.version, true);
        newView.setUint32(SPLASH_HDR_METADATA_DONE_OFFSET + 8, this.width, true);
        newView.setUint32(SPLASH_HDR_METADATA_DONE_OFFSET + 12, this.height, true);
        newView.setUint32(SPLASH_HDR_METADATA_DONE_OFFSET + 16, this.special, true);


        // write metadata
        let offset = 0;
        for (let i = 0; i < this.imageNum; i++) {
            this.dataInfos[i].offset = offset;
            // when update new image to compdata, will auto update compsz and realsz
            // so we no need update it here
            (new Uint8Array(newView.buffer)).set(this.dataInfos[i].gen(), SPLASH_METADATA_OFFSET + (SPLASH_METADATA_BLOCK * i))

            offset += this.dataInfos[i].compsz;
        }

        // write compressed data
        offset = DATA_OFFSET;
        for (let i = 0; i < this.imageNum; i++) {
            (new Uint8Array(newView.buffer)).set(new Uint8Array(this.compData[i]), offset);
            offset += this.compData[i].byteLength;
        }

        return new Blob([newArray], { type: 'application/octet-stream' });
    }

    private convertBMP(imageData: ImageData) {
        const width = imageData.width;
        const height = imageData.height;
        const rowSize = Math.ceil((width * 3) / 4) * 4; // 每行的字节数，必须是4的倍数
        const pixelArraySize = rowSize * height;
        const fileSize = 54 + pixelArraySize;

        const buffer = new ArrayBuffer(fileSize);
        const dataView = new DataView(buffer);

        // BMP 文件头
        dataView.setUint16(0, 0x424D, false); // BM
        dataView.setUint32(2, fileSize, true); // 文件大小
        dataView.setUint32(6, 0, true); // 保留字段
        dataView.setUint32(10, 54, true); // 图像数据的偏移量

        // DIB 头
        dataView.setUint32(14, 40, true); // DIB头的大小
        dataView.setUint32(18, width, true); // 图像宽度
        dataView.setUint32(22, height, true); // 图像高度
        dataView.setUint16(26, 1, true); // 颜色平面数
        dataView.setUint16(28, 24, true); // 位深度（24位）
        dataView.setUint32(30, 0, true); // 压缩方式（无压缩）
        dataView.setUint32(34, pixelArraySize, true); // 图像数据大小
        dataView.setUint32(38, 2835, true); // 水平分辨率（像素/米）
        dataView.setUint32(42, 2835, true); // 垂直分辨率（像素/米）
        dataView.setUint32(46, 0, true); // 调色板颜色数
        dataView.setUint32(50, 0, true); // 重要颜色数

        // 像素数组（BGR格式）
        const offset = 54;
        const data = imageData.data;
        for (let y = 0; y < height; y++) {
            const rowStart = offset + (height - y - 1) * rowSize;
            for (let x = 0; x < width; x++) {
                const pixelStart = (y * width + x) * 4;
                const bmpPixelStart = rowStart + x * 3;
                dataView.setUint8(bmpPixelStart, data[pixelStart + 2]); // Blue
                dataView.setUint8(bmpPixelStart + 1, data[pixelStart + 1]); // Green
                dataView.setUint8(bmpPixelStart + 2, data[pixelStart]); // Red
            }
        }

        return buffer;
    }

    public changeImageByIndex(index : number, imageData: ImageData) {
        console.log("Change image index:", index);

        if (index > this.imageNum) {
            return false;
        }
        console.log("Convert to bmp data");
        const buffer = this.convertBMP(imageData);

        console.log("Compress to gz format");
        const compdata = pako.gzip(buffer);

        // remove time stamp
        compdata[4] = 0;
        compdata[5] = 0;
        compdata[6] = 0;
        compdata[7] = 0;

        console.log("Update realsz and compsz");
        this.dataInfos[index].compsz = compdata.byteLength;
        this.dataInfos[index].realsz = buffer.byteLength;
        this.compData[index] = compdata;

        return true;
    }
}
"""