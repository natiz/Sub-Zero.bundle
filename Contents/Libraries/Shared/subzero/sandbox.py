# coding=utf-8

# restore builtins


def restore_builtins(module, base):
    module.__builtins__ = [x for x in base.__class__.__base__.__subclasses__() if x.__name__ == 'catch_warnings'][0]()._module.__builtins__


def show_callers_locals():
    """Print the local variables in the caller's frame."""
    import inspect
    frame = inspect.currentframe()

    try:
        print frame.f_back.f_globals
        #print dir(frame.f_back)
        #print inspect.getouterframes(frame)
    finally:
        del frame