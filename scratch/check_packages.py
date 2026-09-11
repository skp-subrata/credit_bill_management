pkgs = ['xlrd', 'openpyxl', 'pandas', 'bs4', 'lxml', 'html5lib', 'csv']
for p in pkgs:
    try:
        mod = __import__(p)
        print(f"{p}: INSTALLED ({getattr(mod, '__file__', 'builtin')})")
    except Exception as e:
        print(f"{p}: NOT INSTALLED ({e})")

