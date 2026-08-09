#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <direct.h>
#include <stddef.h>
 
typedef char int8 ;
typedef unsigned char uint8 ;
typedef short int16 ;
typedef unsigned short uint16 ;
typedef int int32 ;
typedef unsigned int uint32 ;
typedef __int64 int64 ;
typedef unsigned __int64 uint64 ;
 
typedef struct tagCPBHEADER
{
	char cp_magic[2] ;		//'CP'
	uint8 cp_version[2] ; 	//CPB文件版本
	uint16 correct[6] ;		//12字节校正用 
	uint8 unknown[32] ;		//未知32字节
	char model[32] ;		//适用的手机型号,如"8730L" 
	char hardVersion[16] ;	//适用的硬件版本号,如"P3"
	char version[64] ;		//适用的版本号,如"4.3.066.P3.140417.8730L"
	char romFrom[256] ;		//
	uint32 imgHdrEndPos ; 	//Image Header停止的位置,这样就能确定Image Header大小
	uint8 reverse[128] ;  	//保留
	uint32 checkSum ;		//校验和（CRC16） 
}CPBHEADER, *LPCPBHEADER ;
 
typedef struct tagIMAGEHEADER
{
    char fileName[64] ;
    uint32 imageOffset ;
    uint32 imageSize ;
    uint32 checkSum ;//CRC16
}IMAGEHEADER, *LPIMAGEHEADER;
 
const uint16 CRC16Tab[256] =
{
	0x0000L, 0x1021L, 0x2042L, 0x3063L,
	0x4084L, 0x50a5L, 0x60c6L, 0x70e7L,
	0x8108L, 0x9129L, 0xa14aL, 0xb16bL,
	0xc18cL, 0xd1adL, 0xe1ceL, 0xf1efL,
	0x1231L, 0x0210L, 0x3273L, 0x2252L,
	0x52b5L, 0x4294L, 0x72f7L, 0x62d6L,
	0x9339L, 0x8318L, 0xb37bL, 0xa35aL,
	0xd3bdL, 0xc39cL, 0xf3ffL, 0xe3deL,
	0x2462L, 0x3443L, 0x0420L, 0x1401L,
	0x64e6L, 0x74c7L, 0x44a4L, 0x5485L,
	0xa56aL, 0xb54bL, 0x8528L, 0x9509L,
	0xe5eeL, 0xf5cfL, 0xc5acL, 0xd58dL,
	0x3653L, 0x2672L, 0x1611L, 0x0630L,
	0x76d7L, 0x66f6L, 0x5695L, 0x46b4L,
	0xb75bL, 0xa77aL, 0x9719L, 0x8738L,
	0xf7dfL, 0xe7feL, 0xd79dL, 0xc7bcL,
	0x48c4L, 0x58e5L, 0x6886L, 0x78a7L,
	0x0840L, 0x1861L, 0x2802L, 0x3823L,
	0xc9ccL, 0xd9edL, 0xe98eL, 0xf9afL,
	0x8948L, 0x9969L, 0xa90aL, 0xb92bL,
	0x5af5L, 0x4ad4L, 0x7ab7L, 0x6a96L,
	0x1a71L, 0x0a50L, 0x3a33L, 0x2a12L,
	0xdbfdL, 0xcbdcL, 0xfbbfL, 0xeb9eL,
	0x9b79L, 0x8b58L, 0xbb3bL, 0xab1aL,
	0x6ca6L, 0x7c87L, 0x4ce4L, 0x5cc5L,
	0x2c22L, 0x3c03L, 0x0c60L, 0x1c41L,
	0xedaeL, 0xfd8fL, 0xcdecL, 0xddcdL,
	0xad2aL, 0xbd0bL, 0x8d68L, 0x9d49L,
	0x7e97L, 0x6eb6L, 0x5ed5L, 0x4ef4L,
	0x3e13L, 0x2e32L, 0x1e51L, 0x0e70L,
	0xff9fL, 0xefbeL, 0xdfddL, 0xcffcL,
	0xbf1bL, 0xaf3aL, 0x9f59L, 0x8f78L,
	0x9188L, 0x81a9L, 0xb1caL, 0xa1ebL,
	0xd10cL, 0xc12dL, 0xf14eL, 0xe16fL,
	0x1080L, 0x00a1L, 0x30c2L, 0x20e3L,
	0x5004L, 0x4025L, 0x7046L, 0x6067L,
	0x83b9L, 0x9398L, 0xa3fbL, 0xb3daL,
	0xc33dL, 0xd31cL, 0xe37fL, 0xf35eL,
	0x02b1L, 0x1290L, 0x22f3L, 0x32d2L,
	0x4235L, 0x5214L, 0x6277L, 0x7256L,
	0xb5eaL, 0xa5cbL, 0x95a8L, 0x8589L,
	0xf56eL, 0xe54fL, 0xd52cL, 0xc50dL,
	0x34e2L, 0x24c3L, 0x14a0L, 0x0481L,
	0x7466L, 0x6447L, 0x5424L, 0x4405L,
	0xa7dbL, 0xb7faL, 0x8799L, 0x97b8L,
	0xe75fL, 0xf77eL, 0xc71dL, 0xd73cL,
	0x26d3L, 0x36f2L, 0x0691L, 0x16b0L,
	0x6657L, 0x7676L, 0x4615L, 0x5634L,
	0xd94cL, 0xc96dL, 0xf90eL, 0xe92fL,
	0x99c8L, 0x89e9L, 0xb98aL, 0xa9abL,
	0x5844L, 0x4865L, 0x7806L, 0x6827L,
	0x18c0L, 0x08e1L, 0x3882L, 0x28a3L,
	0xcb7dL, 0xdb5cL, 0xeb3fL, 0xfb1eL,
	0x8bf9L, 0x9bd8L, 0xabbbL, 0xbb9aL,
	0x4a75L, 0x5a54L, 0x6a37L, 0x7a16L,
	0x0af1L, 0x1ad0L, 0x2ab3L, 0x3a92L,
	0xfd2eL, 0xed0fL, 0xdd6cL, 0xcd4dL,
	0xbdaaL, 0xad8bL, 0x9de8L, 0x8dc9L,
	0x7c26L, 0x6c07L, 0x5c64L, 0x4c45L,
	0x3ca2L, 0x2c83L, 0x1ce0L, 0x0cc1L,
	0xef1fL, 0xff3eL, 0xcf5dL, 0xdf7cL,
	0xaf9bL, 0xbfbaL, 0x8fd9L, 0x9ff8L,
	0x6e17L, 0x7e36L, 0x4e55L, 0x5e74L,
	0x2e93L, 0x3eb2L, 0x0ed1L, 0x1ef0L
};
 
uint32 CRC16(const uint8 *pData, uint32 nSize, uint32 uiCrc)
{
    uint32 i;
 
    for (i=0; i<nSize; i++)
        uiCrc = (uiCrc << 8) ^ (uint16)CRC16Tab[(uint8)(uiCrc >> 8) ^ pData[i]];
    return uiCrc ;
}
 
int32 MkdirRecursive( char* path )
{
	char *p, ch;
	if( access( path, 0 ) == 0 )
		return 0;
	for( p=path; *p; p++ )
	{
		if( p>path && ((*p == '/') || (*p == '\\')) )
		{
			ch = *p ;
			*p = 0;
			if( access( path, 0 ) != 0 )
			{
				if( mkdir( path ) != 0 )
					return -1;
			}
			*p = ch ;
		}
	}
	return mkdir( path );
}
 
void usage(void)
{
    printf("usage: cpbtool.exe\n"
    	"  [-l <CPB文件> <列表文件>]\n\t#列出CPB的所有文件为列表文件.\n"
    	"  [-u <CPB文件> <路径>]\n\t#解压CPB文件到指定目录.\n"
    	"  [-p <型号> <硬件版本> <版本号> <路径> <列表文件> <CPB文件>]\n\t#打包指定目录下的文件为CPB包.\n"
	) ;
	printf("Ex: cpbtool.exe -l ex.cpb list.txt\n") ;
	printf("    cpbtool.exe -u ex.cpb .\\8730L\n") ;
	printf("    cpbtool.exe -p 8730L P3 4.3.066.P3.140417.8730L .\\8730L list.txt new.cpb\n") ;
}
 
void PrintCpbHeader(LPCPBHEADER pHdr)
{
	char buf[512] ;
	printf("CPB version:%d.%d\n", pHdr->cp_version[0], pHdr->cp_version[1]) ;
	strncpy(buf, pHdr->model, sizeof(buf)) ;
	printf("Model:%s\n", buf) ;
	strncpy(buf, pHdr->hardVersion, sizeof(buf)) ;
	printf("HardWare Version:%s\n", buf) ;
	strncpy(buf, pHdr->version, sizeof(buf)) ;
	printf("Version:%s\n", buf) ;
	printf("Header size:%u,every 76 bytes,total %u.\n",
		pHdr->imgHdrEndPos-sizeof(CPBHEADER), (pHdr->imgHdrEndPos-sizeof(CPBHEADER)) / sizeof(IMAGEHEADER)) ;
	printf("checkSum:0x%08X\n\n", pHdr->checkSum) ;
}
 
void CreateListFile(const char *lpszCpb, const char *lpszList)
{
	FILE *fcpb = NULL ;
	FILE *flst = NULL ;
	CPBHEADER cpbHdr ;
	LPIMAGEHEADER pImgHdr = NULL ;
	size_t sz ;
	uint32 nImgSize, nImgCount, i ;
	
	fcpb = fopen(lpszCpb, "rb") ;
	if (fcpb == NULL)
	{
		printf("open “%s” failed!\n", lpszCpb) ;
		return 0 ;
	}
	sz = fread(&cpbHdr, sizeof(cpbHdr), 1, fcpb);
	if(sz != 1 || cpbHdr.cp_magic[0] != 'C' || cpbHdr.cp_magic[1] != 'P' ||
		cpbHdr.imgHdrEndPos < sizeof(cpbHdr))
	{
		fclose(fcpb) ;
		printf("invalid cpb!\n") ;
		return 0;
	}
	if(cpbHdr.cp_version[0] != 0x01 || cpbHdr.cp_version[1] != 0x07)
	{
		printf("1.7 not detected.header should be \"CP\\x01\\x07\".\n") ;
		return ;
	}
	PrintCpbHeader(&cpbHdr) ;
	nImgSize = cpbHdr.imgHdrEndPos - sizeof(CPBHEADER) ;
	nImgCount = (cpbHdr.imgHdrEndPos - sizeof(CPBHEADER)) / sizeof(IMAGEHEADER) ;
	pImgHdr = (LPIMAGEHEADER)malloc(nImgSize) ;
	if(pImgHdr == NULL)
	{
		fclose(fcpb) ;
		printf("malloc %u failed,invalid file!\n", nImgSize) ;
		return 0 ;
	}
	sz = fread(pImgHdr, nImgSize, 1, fcpb) ;
	if(sz != 1)
	{
		free(pImgHdr) ;
		fclose(fcpb) ;
		printf("invalid cpb!\n") ;
		return 0 ;
	}
	flst = fopen(lpszList, "w") ;
	if(flst != NULL)
	{
		for(i=0; i<nImgCount; i++)
			fprintf(flst, "%s\n", pImgHdr[i].fileName) ;
		fclose(flst) ;
		printf("list file '%s' Generated!\n", lpszList) ;
	}
	else
		printf("list file '%s'Generate failed!\n", lpszList) ;
	free(pImgHdr) ;
	fclose(fcpb) ;
	return 0 ;
}
 
void PrintfImageHeader(LPIMAGEHEADER pImgHdr)
{
	char buf[128] ;
	strncpy(buf, pImgHdr->fileName, sizeof(buf)) ;
	printf("FileName:%s\n", buf) ;
	printf("Offset:0x%08X\n", pImgHdr->imageOffset) ;
	printf("Size:0x%08X(%u)\n", pImgHdr->imageSize, pImgHdr->imageSize) ;
	printf("CheckSum:0x%08X\n", pImgHdr->checkSum) ;
}
 
void ImageHeaderCorrectPosSize(LPIMAGEHEADER pImgHdr, int32 idx, uint32 uiCorrect)
{
	uint32 iPos, nSize, iTemp ;
	uint8 bt1, bt2, bt3, bt4 ;
	bt1 = (uint8)idx + (uint8)uiCorrect ;
	bt2 = (uint8)idx + (uint8)(uiCorrect >> 8) ;
	bt3 = (uint8)idx + (uint8)(uiCorrect >> 16) ;
	bt4 = (uint8)idx + (uint8)(uiCorrect >> 24) ;
	iPos = pImgHdr->imageOffset ;
	nSize = pImgHdr->imageSize ;
	iPos = (uint8)(bt3 ^ iPos) | 
		(uint16)((uint8)(bt4 ^ (uint8)(iPos >> 8)) << 8) | 
		(((uint8)(bt1 ^ ((uint32)iPos >> 16)) | 
		(uint16)((uint8)(bt2 ^ (uint8)(iPos >> 24)) << 8)) << 16);
	iTemp = (uint8)(bt3 ^ nSize);
	nSize = iTemp | (uint16)((uint8)(bt4 ^ (uint8)(nSize >> 8)) << 8) | 
		(((uint8)(bt1 ^ ((uint32)nSize >> 16)) | 
		(uint16)((uint8)(bt2 ^ (uint8)(nSize >> 24)) << 8)) << 16);
	pImgHdr->imageOffset = iPos ;
	pImgHdr->imageSize = nSize ;
}
 
void DumpFile(FILE *fcpb, const char *lpszPath, LPIMAGEHEADER pImgHdrs, uint32 nImgCount)
{
	FILE *fImg ;
	char szFile[512] ;
	uint8 *pBuf ;
	uint32 i, iBufSize, nLen, uiCrc = 0;
	if(pImgHdrs == NULL) return ;
	iBufSize = 1024 * 1024 ; //1MiB
	pBuf = (uint8 *)malloc(iBufSize) ;
	if(pBuf == NULL)
	{
		printf("DumpFile Malloc Failed!\n") ;
		return ;
	}
	for(i=0; i<nImgCount; i++)
	{
		PrintfImageHeader(&pImgHdrs[i]) ;
		if(pImgHdrs[i].imageSize == 0) continue ;
		if(fseek(fcpb, pImgHdrs[i].imageOffset, SEEK_SET) != 0)
		{
			printf("Generate “%s” Failed!Cannot seek to:0x%08X\n\n",
				pImgHdrs[i].fileName, pImgHdrs[i].imageOffset) ;
			continue ;
		}
		sprintf(szFile, "%s%s", lpszPath, pImgHdrs[i].fileName) ;
		fImg = fopen(szFile, "wb") ;
		if(fImg == NULL)
		{
			printf("Generate '%s' Failed!\n", szFile) ;
			continue ;
		}
		for(nLen=0, uiCrc=0; (nLen+iBufSize)<=pImgHdrs[i].imageSize; nLen+=iBufSize)
		{
			if(fread(pBuf, iBufSize, 1, fcpb) != 1)
			{
				printf("Generate “%s” Failed!\n\n", pImgHdrs[i].fileName) ;
				break ;
			}
			uiCrc = CRC16(pBuf, iBufSize, uiCrc) ;
			fwrite(pBuf, iBufSize, 1, fImg) ;
		}
		nLen = pImgHdrs[i].imageSize - nLen ;
		if(nLen > 0)
		{
			if(fread(pBuf, nLen, 1, fcpb) == 1)
			{
				uiCrc = CRC16(pBuf, nLen, uiCrc) ;
				fwrite(pBuf, nLen, 1, fImg) ;
			}
			else
				printf("Generate %s Failed!!\n\n", pImgHdrs[i].fileName) ;
		}
		fclose(fImg) ;
		if(uiCrc != pImgHdrs[i].checkSum)
			printf("Verify Failed!Generated %s invalid!wrong cpb!\n\n", pImgHdrs[i].fileName) ;
		else
			printf("%s Generated!\n\n", pImgHdrs[i].fileName) ;
	}
	free(pBuf) ;
}
 
void UnpackCpb(const char *lpszCpb, const char *lpszPath)
{
	FILE *fcpb = NULL;
	CPBHEADER cpbHdr ;
	LPIMAGEHEADER pImgHdr = NULL ;
	size_t sz ;
	uint32 nImgSize, nImgCount, i, uiCrc, uiCorrect ;
	uint64 uiVal64 ;
	char szPath[264] ;
	
	if(lpszPath == NULL || lpszPath[0]=='\0')
	{
		printf("Invalid path\n") ;
		return ;
	}
	strncpy(szPath, lpszPath, sizeof(szPath)) ;
	if(MkdirRecursive(szPath) != 0)
	{
		printf("Create '%s' Failed!\n", lpszPath) ;
		return ;
	}
	sz = strlen(szPath) ;
	if(szPath[sz-1] != '/' && szPath[sz-1] != '\\')
	{
		szPath[sz] = '\\' ;
		szPath[sz+1] = '\0' ;
	}
	
	fcpb = fopen(lpszCpb, "rb") ;
	if (fcpb == NULL)
	{
		printf("Open “%s” Failed!\n", lpszCpb) ;
		return ;
	}
	sz = fread(&cpbHdr, sizeof(cpbHdr), 1, fcpb);
	if(sz != 1 || cpbHdr.cp_magic[0] != 'C' || cpbHdr.cp_magic[1] != 'P' ||
		cpbHdr.imgHdrEndPos < sizeof(cpbHdr))
	{
		fclose(fcpb) ;
		printf("wrong file!\n") ;
		return ;
	}
	if(cpbHdr.cp_version[0] != 0x01 || cpbHdr.cp_version[1] != 0x07)
	{
		printf("Only Supported CPB1.7.magic should be \"CP\\x01\\x07\"\n") ;
		return ;
	}
	uiCorrect = 0 ;
	for(i=0; i<6; i++)
		uiCorrect += cpbHdr.correct[i] ;
	uiVal64 = (uint64)0x66666667 * uiCorrect ;
	uiCorrect = (uint32)((int32)(uiVal64 >> 32)) >> 1 ;
	uiCorrect = (uint16)((uiCorrect >> 31) + uiCorrect) ;
	uiCorrect = (uiCorrect-cpbHdr.correct[3]) | ((uiCorrect-cpbHdr.correct[4]) << 16) ;
	uiCrc = CRC16((uint8 *)&cpbHdr, sizeof(cpbHdr)-4, 0) ;
	PrintCpbHeader(&cpbHdr) ;
	nImgSize = cpbHdr.imgHdrEndPos - sizeof(CPBHEADER) ;
	nImgCount = (cpbHdr.imgHdrEndPos - sizeof(CPBHEADER)) / sizeof(IMAGEHEADER) ;
	pImgHdr = (LPIMAGEHEADER)malloc(nImgSize) ;
	if(pImgHdr == NULL)
	{
		fclose(fcpb) ;
		printf("Malloc %u bytes failed,wrong file!\n", nImgSize) ;
		return ;
	}
	sz = fread(pImgHdr, nImgSize, 1, fcpb) ;
	if(sz != 1)
	{
		free(pImgHdr) ;
		fclose(fcpb) ;
		printf("Invalid CPB File!\n") ;
		return ;
	}
	for(i=0; i<nImgCount; i++)
	{
		ImageHeaderCorrectPosSize(&pImgHdr[i], i, uiCorrect);
		uiCrc = CRC16((uint8 *)&pImgHdr[i], sizeof(IMAGEHEADER), uiCrc) ;
	}
	uiCrc += cpbHdr.cp_version[1] ;
	if(uiCrc != cpbHdr.checkSum)
	{
		free(pImgHdr) ;
		fclose(fcpb) ;
		printf("Verify Failed!Expected:0x%.8X,But:0x%.8X\n",
			cpbHdr.checkSum, uiCrc) ;
		return ;
	}
	DumpFile(fcpb, szPath, pImgHdr, nImgCount) ;
	free(pImgHdr) ;
	fclose(fcpb) ;
	return ;
}
 
void TrimCRLF(char *str)
{
	int32 nLen ;
	nLen = strlen(str) - 1 ;
	for(; nLen>=0; nLen--)
	{
		if(str[nLen]=='\r' || str[nLen]=='\n')
			str[nLen] = '\0' ;
		else
			break ;
	}
}
 
void InitCpbHeader(LPCPBHEADER pCpbHdr, const char *lpszModel, const char *lpszHardVer,
	const char *lpszVersion, const char *lpszFrom)
{
	uint16 arrCorrect[6] = {0x005C, 0x0836, 0x0828, 0x083A, 0x0809, 0x0825} ;
	uint8 unknown[33] = "\x55\x35\x25\x27\x28\x59\x2D\x11\x32\x2D\x24\x3D\x5B\x2B\x3F\x11"
						"\x0C\x16\x07\x01\x11\x16\x10\x03\x06\x13\x03\x1C\x01\x06\x00\x00" ;
	memset(pCpbHdr, 0, sizeof(CPBHEADER)) ;
	pCpbHdr->cp_magic[0] = 'C' ;
	pCpbHdr->cp_magic[1] = 'P' ;
	pCpbHdr->cp_version[0] = 0x01 ;
	pCpbHdr->cp_version[1] = 0x07 ;
	memcpy(pCpbHdr->correct, arrCorrect, sizeof(arrCorrect)) ;
	memcpy(pCpbHdr->unknown, unknown, sizeof(pCpbHdr->unknown)) ;
	strncpy(pCpbHdr->model, lpszModel, sizeof(pCpbHdr->model)) ;
	strncpy(pCpbHdr->hardVersion, lpszHardVer, sizeof(pCpbHdr->hardVersion)) ;
	strncpy(pCpbHdr->version, lpszVersion, sizeof(pCpbHdr->version)) ;
	strncpy(pCpbHdr->romFrom, lpszFrom, sizeof(pCpbHdr->romFrom)) ;
}
 
uint32 WriteImageHeaders(FILE *fcpb, LPIMAGEHEADER pImgHdrs, int32 nCount, uint32 uiCorrect, uint32 uiCrc)
{
	uint32 uiOffset, uiSize ;
	int32 i ;
	for(i=0; i<nCount; i++)
	{
		uiOffset = pImgHdrs[i].imageOffset ;
		uiSize = pImgHdrs[i].imageSize ;
		uiCrc = CRC16(&pImgHdrs[i], sizeof(IMAGEHEADER), uiCrc) ;
		ImageHeaderCorrectPosSize(&pImgHdrs[i], i, uiCorrect) ;
		fwrite(&pImgHdrs[i], sizeof(IMAGEHEADER), 1, fcpb) ;
		pImgHdrs[i].imageOffset = uiOffset ;
		pImgHdrs[i].imageSize = uiSize ;
	}
	return uiCrc ;
}
 
void WriteImages(FILE *fcpb, FILE *fImgs[], LPIMAGEHEADER pImgHdrs, int32 nCount)
{
	int32 i ;
	uint32 iBufSize, nLen, uiCrc ;
	uint8 *pBuf ;
	iBufSize = 1024 * 1024 ; //1MiB
	pBuf = (uint8 *)malloc(iBufSize) ;
	if(pBuf == NULL)
	{
		printf("Failed to get 1MB ram when writing\n") ;
		exit(1) ;
		return ;
	}
	for(i=0; i<nCount; i++)
	{
		printf("Writing %s...\n", pImgHdrs[i].fileName) ;
		uiCrc = 0 ;
		for(nLen=0; (nLen+iBufSize)<=pImgHdrs[i].imageSize; nLen+=iBufSize)
		{
			fread(pBuf, iBufSize, 1, fImgs[i]) ;
			uiCrc = CRC16(pBuf, iBufSize, uiCrc) ;
			fwrite(pBuf, iBufSize, 1, fcpb) ;
		}
		nLen = pImgHdrs[i].imageSize - nLen ;
		if(nLen > 0)
		{
			fread(pBuf, nLen, 1, fImgs[i]) ;
			uiCrc = CRC16(pBuf, nLen, uiCrc) ;
			fwrite(pBuf, nLen, 1, fcpb) ;
		}
		pImgHdrs[i].checkSum = uiCrc ;
	}
	free(pBuf) ;
}
 
void PackCpb(LPCPBHEADER pCpbHdr, const char *lpszPath, const char *lpszList, const char *lpszCpb)
{
#define MAX_IMG	500
	FILE *flst = NULL ;
	FILE *fcpb = NULL ;
	FILE *fImgs[MAX_IMG] ;
	char szPath[260], szFile[512] ;
	LPIMAGEHEADER pImgHdr = NULL ;
	int32 i, nCount ;
	uint32 uiCrc, uiCorrect, uiSize ;
	uint64 uiVal64 ;
	
	if(lpszPath == NULL || lpszPath[0]=='\0' || access(lpszPath, 0) != 0)
	{
		printf("'%s' invalid path!\n", lpszPath) ;
		return ;
	}
	strncpy(szPath, lpszPath, sizeof(szPath)) ;
	uiSize = strlen(szPath) ;
	if(szPath[uiSize-1] != '/' && szPath[uiSize-1] != '\\')
	{
		szPath[uiSize] = '\\' ;
		szPath[uiSize+1] = '\0' ;
	}
	//在此之前确保已经调用InitCpbHeader函数 
	uiCorrect = 0 ;
	for(i=0; i<6; i++)
		uiCorrect += pCpbHdr->correct[i] ;
	uiVal64 = (uint64)0x66666667 * uiCorrect ;
	uiCorrect = (uint32)((int32)(uiVal64 >> 32)) >> 1 ;
	uiCorrect = (uint16)((uiCorrect >> 31) + uiCorrect) ;
	uiCorrect = (uiCorrect-pCpbHdr->correct[3]) | ((uiCorrect-pCpbHdr->correct[4]) << 16) ;
	
	if(access( lpszPath, 0 ) != 0)
	{
		printf("Path '%s' cannot access!\n", lpszPath) ;
		return ;
	}
	flst = fopen(lpszList, "r") ;
	if(flst == NULL)
	{
		printf("list file '%s' open failed!\n", lpszList) ;
		return ;
	}
	fcpb = fopen(lpszCpb, "wb") ;
	if(fcpb == NULL)
	{
		fclose(flst) ;
		printf("Create '%s' Failed!\n", lpszCpb) ;
		return ;
	}
	pImgHdr = malloc(sizeof(IMAGEHEADER) * MAX_IMG) ;
	if(pImgHdr == NULL)
	{
		fclose(flst) ;
		fclose(fcpb) ;
		printf("Failed to malloc!\n") ;
		return ;
	}
	
	for(nCount=0; nCount<MAX_IMG && fgets(pImgHdr[nCount].fileName, sizeof(pImgHdr[nCount].fileName)-1, flst); )
	{
		TrimCRLF(pImgHdr[nCount].fileName) ;
		sprintf(szFile, "%s%s", szPath, pImgHdr[nCount].fileName) ;
		fImgs[nCount] = fopen(szFile, "rb") ;
		if(fImgs[nCount])
		{
			if(fseek(fImgs[nCount], 0, SEEK_END) != 0)
			{
				printf("file '%s'seek failed!\n", szFile) ;
				continue ;
			}
			pImgHdr[nCount].imageOffset += sizeof(IMAGEHEADER) ;
			pImgHdr[nCount].imageSize = ftell(fImgs[nCount]) ;
			if((int32)pImgHdr[nCount].imageSize == -1)
			{
				printf("get file '%s'  size failed!\n", szFile) ;
				continue ;
			}
			fseek(fImgs[nCount], 0, SEEK_SET) ;
			nCount++ ;
		}
		else printf("file '%s' open failed!\n", szFile) ;
	}
	pCpbHdr->imgHdrEndPos = sizeof(CPBHEADER) + nCount * sizeof(IMAGEHEADER) ;
	uiCrc = CRC16((uint8 *)pCpbHdr, sizeof(CPBHEADER)-4, 0) ;
	fwrite(pCpbHdr, sizeof(CPBHEADER), 1, fcpb) ; //写入头
	fwrite(pImgHdr, sizeof(IMAGEHEADER)*nCount, 1, fcpb) ; //写入映像文件头 
	WriteImages(fcpb, fImgs, pImgHdr, nCount) ;
	fseek(fcpb, sizeof(CPBHEADER), SEEK_SET) ;
	uiCrc = WriteImageHeaders(fcpb, pImgHdr, nCount, uiCorrect, uiCrc) ;
	uiCrc += pCpbHdr->cp_version[1] ;
	fseek(fcpb, offsetof(CPBHEADER, checkSum), SEEK_SET) ;
	fwrite(&uiCrc, 4, 1, fcpb) ;
	for(i=0; i<nCount; i++)
		fclose(fImgs[i]) ;
	free(pImgHdr) ;
	fclose(flst) ;
	fclose(fcpb) ;
}
 
int main(int argc, char *argv[])
{
	char *lpszCpb = NULL ;
	char *lpszPath = NULL ;
	char *lpszList = NULL ;
	char *lpszModel = NULL ;
	char *lpszHardVer = NULL ;
	char *lpszVersion = NULL ;
	CPBHEADER cpbHdr ;
	
	if(argc < 4)
	{
		usage() ;
		return 0 ;
	}
	switch(argv[1][1])
	{
	case 'l':
	case 'L':
		lpszCpb = argv[2] ;
		lpszList = argv[3] ;
		CreateListFile(lpszCpb, lpszList) ;
		break ;
		
	case 'u':
	case 'U':
		lpszCpb = argv[2] ;
		lpszPath = argv[3] ;
		UnpackCpb(lpszCpb, lpszPath) ;
		break ;
		
	case 'p':
	case 'P':
		if(argc < 8)
		{
			usage() ;
			return 0 ;
		}
		lpszModel = argv[2] ;
		lpszHardVer = argv[3] ;
		lpszVersion = argv[4] ;
		lpszPath = argv[5] ;
		lpszList = argv[6] ;
		lpszCpb = argv[7] ;
		InitCpbHeader(&cpbHdr, lpszModel, lpszHardVer, lpszVersion, "D:\\image") ;
		PackCpb(&cpbHdr, lpszPath, lpszList, lpszCpb) ;
		break ;
		
	default:
		usage() ;
		return 0 ;
	}
	return 0 ;
}
static PyObject* c_extract(PyObject* self, PyObject* args) {
    const char* filepath;
    const char* output;

    if (!PyArg_ParseTuple(args, "ss", &filepath, &output)) {
        return NULL;
    }
    UnpackCpb(filepath, output);
    Py_RETURN_NONE;
}

static PyMethodDef MyMethods[] = {
    {"extract", c_extract, METH_VARARGS, "extract cpb files"},
    {NULL, NULL, 0, NULL}
};
static struct PyModuleDef cpb_file = {
    PyModuleDef_HEAD_INIT, "cpb_file", NULL, -1, MyMethods
};
PyMODINIT_FUNC PyInit_cpb_file(void) {
    return PyModule_Create(&cpb_file);
}