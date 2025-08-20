#include <Python.h>
#include "utils.h"
int extract_ext4(extract_args_struct args);
static PyObject* ext4_extractor(PyObject* self, PyObject* args) {

    char *config_dir, *mountpoint, *filename, *directory;
    char *image_type;
    int blocksize, android_configure_only;
    extract_args_struct arguments;
    if (!PyArg_ParseTuple(args, "ssssisp", &config_dir, &mountpoint, &filename, &directory, &blocksize, &image_type, &android_configure_only)) {
        return NULL;
    }
    arguments.config_dir = config_dir;
    arguments.mountpoint = mountpoint;
    arguments.filename = filename;
    arguments.directory = directory;
    arguments.image_type = image_type;
    arguments.blocksize = blocksize ? blocksize:0;
    arguments.android_configure_only = android_configure_only;
    int return_code = extract_ext4(arguments);
    free(config_dir);
    free(mountpoint);
    free(filename);
    free(directory);
    free(image_type);
    return Py_BuildValue("i", return_code);

}


static PyMethodDef Methods[] = {

    {"ext4_extractor", ext4_extractor, METH_VARARGS, "Extract ext4 images"},

    {NULL, NULL, 0, NULL}

};


static PyModuleDef libutils = {

    PyModuleDef_HEAD_INIT,

    "libutils",

    "MIO-KITCHEN C Module.",

    -1,

    Methods

};


PyMODINIT_FUNC PyInit_libutils(void) {

    return PyModule_Create(&libutils);

}