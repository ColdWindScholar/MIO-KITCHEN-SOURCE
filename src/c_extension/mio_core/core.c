#define PY_SSIZE_T_CLEAN
#include <Python.h>
static PyObject* c_extract(PyObject* self, PyObject* args) {
    const char* filepath;
    const char* output;

    if (!PyArg_ParseTuple(args, "ss", &filepath, &output)) {
        return NULL;
    }
    Py_BEGIN_ALLOW_THREADS
    printf(filepath, output);
    Py_END_ALLOW_THREADS
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