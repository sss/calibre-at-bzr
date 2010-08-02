#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <wand/MagickWand.h>

#include "magick_constants.h"

PyObject* magick_set_exception(MagickWand *wand) {
    ExceptionType ext;
    char *desc = MagickGetException(wand, &ext);
    PyErr_SetString(PyExc_Exception, desc);
    MagickClearException(wand);
    desc = MagickRelinquishMemory(desc);
    return NULL;
}

// Image object definition {{{
typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    MagickWand *wand;

} magick_Image;

static void
magick_Image_dealloc(magick_Image* self)
{
    if (self->wand != NULL) self->wand = DestroyMagickWand(self->wand);
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
magick_Image_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    magick_Image *self;

    self = (magick_Image *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->wand = NewMagickWand();
        if (self->wand == NULL || self->wand < 0) { 
            PyErr_SetString(PyExc_Exception, "Failed to allocate wand. Did you initialize ImageMgick?");
            self->wand = NULL;
            Py_DECREF(self);
            return NULL;
        }
    }

    return (PyObject *)self;
}

static PyObject *
magick_Image_load(magick_Image *self, PyObject *args, PyObject *kwargs) {
    const char *data;
	Py_ssize_t dlen;
    
    if (!PyArg_ParseTuple(args, "s#", &data, &dlen)) return NULL;

    if (!MagickReadImageBlob(self->wand, data, dlen))
        return magick_set_exception(self->wand);

    Py_RETURN_NONE;
}

static PyObject *
magick_Image_export(magick_Image *self, PyObject *args, PyObject *kwargs) {
    char *fmt;
    unsigned char *data;
    PyObject *ans;
    size_t len = 0;
    
    if (!PyArg_ParseTuple(args, "s", &fmt)) return NULL;

    if (!MagickSetFormat(self->wand, fmt)) {
        PyErr_SetString(PyExc_ValueError, "Unknown image format");
        return NULL;
    }

    data = MagickGetImageBlob(self->wand, &len);
    if (data == NULL || len < 1) 
        return magick_set_exception(self->wand);

    ans = Py_BuildValue("s#", data, len);
    data = MagickRelinquishMemory(data);

    return ans;
}



static PyObject *
magick_Image_size_getter(magick_Image *self, void *closure) {
    size_t width, height;
    width = MagickGetImageWidth(self->wand);
    height = MagickGetImageHeight(self->wand);
    return Py_BuildValue("II", width, height);
}

static int
magick_Image_size_setter(magick_Image *self, PyObject *val, void *closure) {
    Py_ssize_t width, height;
    FilterTypes filter;
    double blur;

    if (val == NULL) {
        return -1;
        PyErr_SetString(PyExc_TypeError, "Cannot delete image size");
    }

    if (!PySequence_Check(val) || PySequence_Length(val) < 4) {
        PyErr_SetString(PyExc_TypeError, "Must use at least a 4 element sequence to set size");
        return -1;
    }

    width = PyInt_AsSsize_t(PySequence_ITEM(val, 0));
    height = PyInt_AsSsize_t(PySequence_ITEM(val, 1));
    filter = (FilterTypes)PyInt_AsSsize_t(PySequence_ITEM(val, 2));
    blur = PyFloat_AsDouble(PySequence_ITEM(val, 2));

    if (PyErr_Occurred()) {
        PyErr_SetString(PyExc_TypeError, "Width, height, filter or blur not a number");
        return -1;
    }

    if ( filter <= UndefinedFilter || filter >= SentinelFilter) {
        PyErr_SetString(PyExc_ValueError, "Invalid filter");
        return -1;
    }

    if (!MagickResizeImage(self->wand, width, height, filter, blur)) {
        magick_set_exception(self->wand);
        return -1;
    }

    return 0;
    
}


static PyObject *
magick_Image_format_getter(magick_Image *self, void *closure) {
    const char *fmt;
    fmt = MagickGetImageFormat(self->wand);
    return Py_BuildValue("s", fmt);
}


static PyMethodDef magick_Image_methods[] = {
    {"load", (PyCFunction)magick_Image_load, METH_VARARGS,
     "Load an image from a byte buffer (string)"
    },

    {"export", (PyCFunction)magick_Image_export, METH_VARARGS,
     "export(format) -> bytestring\n\n Export the image as the specified format"
    },

    {NULL}  /* Sentinel */
};

static PyGetSetDef  magick_Image_getsetters[] = {
    {(char *)"size", 
     (getter)magick_Image_size_getter, (setter)magick_Image_size_setter,
     (char *)"Image size (width, height). When setting pass in (width, height, filter, blur). See MagickResizeImage docs.",
     NULL},

    {(char *)"format", 
     (getter)magick_Image_format_getter, NULL,
     (char *)"Image format",
     NULL},

    {NULL}  /* Sentinel */
};

static PyTypeObject magick_ImageType = {
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "magick.Image",            /*tp_name*/
    sizeof(magick_Image),      /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)magick_Image_dealloc, /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    0,                         /*tp_repr*/
    0,                         /*tp_as_number*/
    0,                         /*tp_as_sequence*/
    0,                         /*tp_as_mapping*/
    0,                         /*tp_hash */
    0,                         /*tp_call*/
    0,                         /*tp_str*/
    0,                         /*tp_getattro*/
    0,                         /*tp_setattro*/
    0,                         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT|Py_TPFLAGS_BASETYPE,        /*tp_flags*/
    "Images",                  /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    magick_Image_methods,             /* tp_methods */
    0,             /* tp_members */
    magick_Image_getsetters,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,      /* tp_init */
    0,                         /* tp_alloc */
    magick_Image_new,                 /* tp_new */
};



// }}}

// Module functions {{{

static PyObject *
magick_genesis(PyObject *self, PyObject *args)
{
    MagickWandGenesis();
    Py_RETURN_NONE;
}

static PyObject *
magick_terminus(PyObject *self, PyObject *args)
{
    MagickWandTerminus();
    Py_RETURN_NONE;
}

static PyMethodDef magick_methods[] = {
    {"genesis", magick_genesis, METH_VARARGS,
    "genesis()\n\n"
            "Initializes ImageMagick.\n"
    		"Must be called before any other use of this module is made. "
    },

    {"terminus", magick_terminus, METH_VARARGS,
    "terminus()\n\n"
            "Cleans up ImageMagick memory structures.\n"
    		"Must be called after you are done using this module. You can call genesis() again after this to resume using the module."
    },

    {NULL}  /* Sentinel */
};
// }}}

// Module initialization {{{
PyMODINIT_FUNC
initmagick(void) 
{
    PyObject* m;

    if (PyType_Ready(&magick_ImageType) < 0)
        return;

    m = Py_InitModule3("magick", magick_methods,
                       "Wrapper for the ImageMagick imaging library");

    Py_INCREF(&magick_ImageType);
    PyModule_AddObject(m, "Image", (PyObject *)&magick_ImageType);

    magick_add_module_constants(m);
}
// }}}
