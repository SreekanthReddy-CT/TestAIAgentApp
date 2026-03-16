#!/usr/bin/env python3
import os
import sys
import shutil
import re
import argparse
from pathlib import Path
import tempfile
import uuid
import datetime


def atomic_replace(file_path: Path, new_text: str):
    """Writes text to a temporary file, then atomically replaces the target file."""
    fd, tmp_path = tempfile.mkstemp(dir=str(file_path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(new_text)
        os.replace(tmp_path, str(file_path))
    finally:
        # cleanup if something went wrong and tmp still exists
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def perform_ordered_replacements(text: str, app_name: str, final_struct_name: str, bundle_id: str) -> str:
    """Applies strict ordered text replacements to avoid partial renames.

    Rules:
    1) Replace BaseTemplateApp -> FINAL_STRUCT_NAME
    2) Replace BaseTemplate -> AppName
    3) Replace PRODUCT_BUNDLE_IDENTIFIER values (preserve quoting)
    """
    # 1. Replace BaseTemplateApp first
    text = text.replace("BaseTemplateApp", final_struct_name)

    # 2. Then replace BaseTemplate
    text = text.replace("BaseTemplate", app_name)

    # 3. Update PRODUCT_BUNDLE_IDENTIFIER preserving quotes and semicolon
    if bundle_id:
        text = re.sub(
            r'(PRODUCT_BUNDLE_IDENTIFIER\s*=\s*)(".*?"|[^;]+)(;)',
            rf'\1"{bundle_id}"\3',
            text,
        )

    return text


def merge_workdir_into_target(work_dir: Path, target_dir: Path):
    """Move contents from work_dir into target_dir with backups of overwritten entries.
    If anything fails during the merge, attempt to restore from backups.
    """
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    backup_dir = target_dir / f".backup_gen_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    moved = []
    try:
        for item in work_dir.iterdir():
            dest = target_dir / item.name
            # If destination exists, move it to backup
            if dest.exists():
                shutil.move(str(dest), str(backup_dir / dest.name))
            # Move new item into place
            shutil.move(str(item), str(dest))
            moved.append(dest)
        # If we reach here, merge succeeded; remove backup
        shutil.rmtree(backup_dir, ignore_errors=True)
    except Exception as e:
        # Attempt rollback: remove moved items and restore backups
        for m in moved:
            try:
                if m.exists():
                    if m.is_dir():
                        shutil.rmtree(m)
                    else:
                        m.unlink()
            except Exception:
                pass
        # restore backups
        for b in backup_dir.iterdir():
            try:
                shutil.move(str(b), str(target_dir / b.name))
            except Exception:
                pass
        raise RuntimeError(f"Merge failed: {e}")


def safe_copy_template_to_workdir(template_dir: Path, work_dir: Path):
    """Copy the template contents (not the parent folder) into work_dir."""
    work_dir.mkdir(parents=True, exist_ok=True)
    for item in template_dir.iterdir():
        dest = work_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)


def main():
    parser = argparse.ArgumentParser(description="Generate iOS Project from BaseTemplate")
    parser.add_argument("--name", required=True, help="The App Name (PascalCase)")
    parser.add_argument("--bundle-id", required=True, help="The Bundle Identifier")
    parser.add_argument("--dir", default=".", help="Target directory (default: current directory)")

    args = parser.parse_args()

    app_name = args.name
    bundle_id = args.bundle_id
    target_dir = Path(args.dir).resolve()

    # Calculate FINAL_APP_STRUCT_NAME
    final_struct_name = app_name if app_name.endswith("App") else f"{app_name}App"

    # Path to the source template (assuming script is in /scripts, template in /resources/BaseTemplate)
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    template_dir = repo_root / "resources" / "BaseTemplate"

    if not template_dir.exists():
        print(f"Error: Template directory not found at {template_dir}")
        sys.exit(1)

    print(f"🚀 Generating {app_name} into temporary workspace...")

    # Create isolated work directory
    tmp_root = Path(tempfile.mkdtemp(prefix="gen_ios_"))
    work_dir = tmp_root / uuid.uuid4().hex
    try:
        # Copy template contents into workdir (so target_dir stays untouched until verified)
        safe_copy_template_to_workdir(template_dir, work_dir)

        # Step 5.2 & 5.3: Rename Primary Folders inside workdir
        folders_to_rename = [
            (work_dir / "BaseTemplate", work_dir / app_name),
            (work_dir / "BaseTemplate.xcodeproj", work_dir / f"{app_name}.xcodeproj"),
            (work_dir / "BaseTemplateTests", work_dir / f"{app_name}Tests"),
            (work_dir / "BaseTemplateUITests", work_dir / f"{app_name}UITests"),
        ]

        for old_path, new_path in folders_to_rename:
            if old_path.exists():
                old_path.rename(new_path)

        # Step 5.5, 5.6, 5.7: Rename Specific Files inside workdir
        files_to_rename = [
            (work_dir / f"{app_name}.xcodeproj" / "xcshareddata" / "xcschemes" / "BaseTemplate.xcscheme",
             work_dir / f"{app_name}.xcodeproj" / "xcshareddata" / "xcschemes" / f"{app_name}.xcscheme"),
            (work_dir / app_name / "BaseTemplateApp.swift", work_dir / app_name / f"{final_struct_name}.swift"),
            (work_dir / f"{app_name}Tests" / "BaseTemplateTests.swift", work_dir / f"{app_name}Tests" / f"{app_name}Tests.swift"),
            (work_dir / f"{app_name}UITests" / "BaseTemplateUITests.swift", work_dir / f"{app_name}UITests" / f"{app_name}UITests.swift"),
            (work_dir / f"{app_name}UITests" / "BaseTemplateUITestsLaunchTests.swift", work_dir / f"{app_name}UITests" / f"{app_name}UITestsLaunchTests.swift"),
        ]

        for old_path, new_path in files_to_rename:
            if old_path.exists():
                new_path.parent.mkdir(parents=True, exist_ok=True)
                old_path.rename(new_path)

        # Step 5.4 & 5.8: Update File Contents globally in workdir
        extensions_to_modify = {".swift", ".pbxproj", ".xcscheme", ".plist", ".md", ".xml"}

        for filepath in work_dir.rglob("*"):
            if filepath.is_file() and filepath.suffix in extensions_to_modify:
                try:
                    content = filepath.read_text(encoding="utf-8")
                    if "BaseTemplate" in content or "PRODUCT_BUNDLE_IDENTIFIER" in content:
                        updated_content = perform_ordered_replacements(content, app_name, final_struct_name, bundle_id)
                        if content != updated_content:
                            atomic_replace(filepath, updated_content)
                except Exception as e:
                    print(f"Warning: Could not process {filepath}: {e}")

        # Step 6: Verification inside workdir
        print("🔍 Running verification...")
        leftovers = []
        for filepath in work_dir.rglob("*"):
            if filepath.is_file() and filepath.suffix in extensions_to_modify:
                try:
                    content = filepath.read_text(encoding="utf-8")
                    if "BaseTemplate" in content:
                        leftovers.append(filepath.relative_to(work_dir))
                except Exception:
                    pass

        if leftovers:
            print("❌ Verification failed — leftover occurrences of 'BaseTemplate' found:")
            for p in leftovers:
                print(f" - {p}")
            raise RuntimeError("Verification failed")

        # Merge into target directory with backup of overwritten items
        print(f"📦 Merging generated project into {target_dir} ...")
        target_dir.mkdir(parents=True, exist_ok=True)
        merge_workdir_into_target(work_dir, target_dir)

        print(f"✅ Success! {app_name} is ready at {target_dir}")
    except Exception as e:
        print(f"Error: {e}")
        print("No changes were applied to the target directory.")
        sys.exit(1)
    finally:
        # Cleanup working temporary directory
        try:
            if tmp_root.exists():
                shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
