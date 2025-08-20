#include <Python.h>
#include "include/utils.h"

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sparse/sparse.h>
#include <sparse_file.h>
#ifndef O_BINARY
#define O_BINARY 0
#endif
struct sparse_file;

// s = str , i = int, p = bool
int extract_ext4(extract_args_struct args);
static PyObject* ext4_extractor(PyObject *self, PyObject* args, PyObject* kwargs) {

    char *config_dir, *mountpoint, *filename, *directory;
    char *image_type, *part_name;
    int blocksize, android_configure_only;
    char *kwlist[] = {
        "config_dir", "mountpoint", "filename", "directory", "blocksize", "image_type", "android_configure_only", "part_name",NULL
    };
    extract_args_struct arguments;
    if (!PyArg_ParseTupleAndKeywords(args,kwargs, "ssssisps",kwlist ,&config_dir, &mountpoint, &filename, &directory, &blocksize, &image_type, &android_configure_only, &part_name)) {
        return NULL;
    }
    arguments.config_dir = config_dir;
    arguments.mountpoint = mountpoint;
    arguments.filename = filename;
    arguments.directory = directory;
    arguments.image_type = image_type;
    arguments.blocksize = blocksize ?:0;
    arguments.android_configure_only = android_configure_only;
    arguments.part_name = part_name;
    return Py_BuildValue("i", extract_ext4(arguments));
}


static PyObject* simg2img(PyObject* self, PyObject* args,  PyObject* kwargs) {
    PyObject * sparse_file_list = NULL;
    int in;
    char * output_filename;
    char *kwlist[] = {
        "sparse_file_list", "output_filename",NULL
    };
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Os", kwlist, &sparse_file_list, &output_filename)) {
        return NULL;
    }
    ssize_t sparse_file_list_len = PySequence_Size(sparse_file_list);
    PyObject* seq = PySequence_Fast(sparse_file_list, "split sparse filenames.");
    int out = open(output_filename, O_WRONLY | O_CREAT | O_TRUNC | O_BINARY, 0664);
    if (out < 0) {
        fprintf(stderr, "Cannot open output file %s\n", output_filename);
        return Py_BuildValue("i", EXIT_FAILURE);
    }
    for (int i =0; i < sparse_file_list_len; ++i) {
        PyObject* item = PySequence_Fast_GET_ITEM(seq, i);
        const char * sparse_file_name = PyUnicode_AsUTF8(item);
        printf("Handling: %s\n", sparse_file_name);
        if (strcmp(sparse_file_name, "-") == 0) {
            in = STDIN_FILENO;
        } else {
            in = open(sparse_file_name, O_RDONLY | O_BINARY);
            if (in < 0) {
                fprintf(stderr, "Cannot open input file %s\n", sparse_file_name);
            return Py_BuildValue("i",EXIT_FAILURE);
            }
        }

        struct sparse_file *s = sparse_file_import(in, true, false);
        if (!s) {
            fprintf(stderr, "Failed to read sparse file\n");
            return Py_BuildValue("i",EXIT_FAILURE);
        }

        if (lseek(out, 0, SEEK_SET) == -1) {
            perror("lseek failed");
            return Py_BuildValue("i",EXIT_FAILURE);
        }

        if (sparse_file_write(s, out, false, false, false) < 0) {
            fprintf(stderr, "Cannot write output file\n");
            return Py_BuildValue("i",EXIT_FAILURE);
        }
        sparse_file_destroy(s);
        close(in);
    }
    close(out);
    return Py_BuildValue("i", 0);
}


static PyMethodDef Methods[] = {

    {"ext4_extractor", (PyCFunction)ext4_extractor, METH_VARARGS | METH_KEYWORDS, "Extract ext4 images"},
    {"simg2img", (PyCFunction)simg2img, METH_VARARGS | METH_KEYWORDS, "Sparse or split files to raw."},
    {NULL, NULL, 0, NULL}
};


static PyModuleDef libutils = {
    PyModuleDef_HEAD_INIT,
    "libutils",
    "MIO-KITCHEN C Module.",
    -1,
    Methods
};


PyMODINIT_FUNC PyInit_libutils(void) {return PyModule_Create(&libutils);}