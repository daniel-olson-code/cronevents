import os, sys, json, importlib


def main():
    try:
        # get module
        og_module = module = sys.argv[-4]

        # get function name
        func = sys.argv[-3]

        # get args
        with open(sys.argv[-2], "r") as f:
            args = json.load(f)
        try:
            os.remove(sys.argv[-2])
        except Exception as e:
            print('Error deleting ', sys.argv[-2], e)

        # get kwargs
        with open(sys.argv[-1], "r") as f:
            kwargs = json.load(f)
        try:
            os.remove(sys.argv[-1])
        except Exception as e:
            print('Error deleting ', sys.argv[-1], e)

        # print(module, func, args, kwargs)

        # import module
        module = importlib.import_module(module)

        # call function
        if hasattr(module, func):
            getattr(module, func)(*args, **kwargs)
        else:
            print(f"Function {func} not found in module {og_module}")
            # sys.exit(1)
    finally:
        try:
            os.remove(sys.argv[-2])
        except:
            pass
        try:
            os.remove(sys.argv[-1])
        except:
            pass


if __name__ == "__main__":
    main()










