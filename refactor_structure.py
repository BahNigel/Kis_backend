import os
import shutil
import re
from pathlib import Path

root = Path(__file__).parent.resolve()
inner_project = root / "kis"   # your default Django inner project folder
config_dir = root / "config"

def safe_mkdir(path):
    path.mkdir(parents=True, exist_ok=True)

def safe_touch(path, content=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
        if content:
            path.write_text(content)

def safe_move(src, dst):
    try:
        if src.exists() and not dst.exists():
            shutil.move(str(src), str(dst))
    except Exception as e:
        print(f"⚠️ Skipped moving {src} → {dst}: {e}")

print("🔧 Refactoring Django layout to enterprise structure...\n")

# 1) Move inner project to config/
if inner_project.exists() and not config_dir.exists():
    shutil.move(str(inner_project), str(config_dir))
    print(f"✅ Moved '{inner_project}' → '{config_dir}'")
else:
    print("ℹ️ 'config/' already exists or 'kis/' not found, skipping move.")

# 2) Setup config/settings structure
settings_dir = config_dir / "settings"
safe_mkdir(settings_dir)

base_py = settings_dir / "base.py"
old_settings_py = config_dir / "settings.py"

if old_settings_py.exists():
    safe_move(old_settings_py, base_py)
else:
    safe_touch(base_py, "# Shared base settings\n")

for name in ["__init__.py", "local.py", "production.py"]:
    safe_touch(settings_dir / name)

safe_touch(config_dir / "__init__.py")

# 3) Create top-level folders
for folder in ["apps", "common", "docs/decisions", "scripts", "tests", "requirements"]:
    safe_mkdir(root / folder)

safe_touch(root / "apps/__init__.py")

# 4) Common utilities
for name in ["pagination.py", "permissions.py", "exceptions.py", "utils.py", "middleware.py", "__init__.py"]:
    safe_touch(root / f"common/{name}")

# 5) Docs & scripts
safe_touch(root / "docs/api_style_guide.md")
safe_touch(root / "docs/openapi_schema.yaml")
safe_touch(root / "scripts/manage.sh")
safe_touch(root / "scripts/seed_data.py")

# 6) Tests
for name in ["__init__.py", "test_api_contracts.py", "test_performance.py"]:
    safe_touch(root / f"tests/{name}")

# 7) Requirements
for name in ["base.txt", "dev.txt", "prod.txt"]:
    safe_touch(root / f"requirements/{name}")

# 8) Update DJANGO_SETTINGS_MODULE in manage.py, asgi.py, wsgi.py
targets = [
    root / "manage.py",
    config_dir / "asgi.py",
    config_dir / "wsgi.py",
]

for f in targets:
    if f.exists():
        text = f.read_text()
        new_text = re.sub(
            r"DJANGO_SETTINGS_MODULE\s*=\s*['\"]([A-Za-z0-9_.]+)['\"]",
            "DJANGO_SETTINGS_MODULE = 'config.settings.base'",
            text
        )
        if new_text != text:
            f.write_text(new_text)
            print(f"✅ Updated {f.name} → config.settings.base")
    else:
        print(f"⚠️ Skipped missing {f}")

print("\n✅ Refactor complete!\n")
print("Your new structure (top-level):")
for p in sorted(root.iterdir()):
    if p.is_dir():
        print(f"📁 {p.name}/")
    else:
        print(f"📄 {p.name}")
print("\nNext steps:")
print("1. Open config/settings/base.py and configure your database, apps, middleware, etc.")
print("2. Run: python manage.py check")
print("3. Then: python manage.py runserver")
