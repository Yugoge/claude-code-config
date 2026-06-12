import shutil, glob, os
work = "/dev/shm/dev-workspace/dot-claude/tests/generated/20260611-100500/_work"
keep = {"_cleanup.py"}
for p in glob.glob(work + "/*"):
    b = os.path.basename(p)
    if b in keep:
        continue
    if os.path.isdir(p):
        shutil.rmtree(p, ignore_errors=True)
    else:
        try:
            os.remove(p)
        except OSError:
            pass
print("cleaned. remaining:", [x for x in os.listdir(work)])
