# https://github.com/Huang-junsen/py-xiaozhi/blob/main/src/utils/system_info.py
# Handle opus dynamic library before importing opuslib
import ctypes
import os
import sys


def setup_opus():
    """Set up opus dynamic library"""
    if hasattr(sys, "_opus_loaded"):
        print("opus library already loaded by other components")
        return True

    # Get path to opus.dll
    # Development environment path
    # Assuming system_info.py is in src/utils directory, need to go up three levels to reach project root
    opus_path = os.path.join(os.path.dirname(__file__), "libs", "windows", "opus.dll")

    # Check if file exists
    if os.path.exists(opus_path):
        print(f"Found opus library file: {opus_path}")
    else:
        print(f"Warning: opus library file does not exist at path: {opus_path}")
        # Try to find in other possible locations
        if getattr(sys, "frozen", False):
            alternate_path = os.path.join(os.path.dirname(sys.executable), "opus.dll")
            if os.path.exists(alternate_path):
                opus_path = alternate_path
                print(f"Found opus library file in alternate location: {opus_path}")

    # Preload opus.dll
    try:
        opus_lib = ctypes.cdll.LoadLibrary(opus_path)
        print(f"Successfully loaded opus library: {opus_path}")
        sys._opus_loaded = True
        # Immediately patch find_library after successful load
        _patch_find_library("opus", opus_path)
        return True
    except Exception as e:
        print(f"Failed to load opus library: {e}")

        # Try to find using system path
        try:
            if sys.platform == "win32":
                ctypes.cdll.LoadLibrary("opus")
                print("Loaded opus library from system path")
                sys._opus_loaded = True
                return True
            elif sys.platform == "darwin":  # macOS
                ctypes.cdll.LoadLibrary("libopus.dylib")
                print("Loaded libopus.dylib from system path")
                sys._opus_loaded = True
                return True
            else:  # Linux and other Unix systems
                # Try several common library names
                for lib_name in ["libopus.so.0", "libopus.so", "libopus.so.0.8.0"]:
                    try:
                        ctypes.cdll.LoadLibrary(lib_name)
                        print(f"Loaded {lib_name} from system path")
                        sys._opus_loaded = True
                        return True
                    except:
                        continue
        except Exception as e2:
            print(f"Failed to load opus library from system path: {e2}")

        print("Ensure opus dynamic library is correctly installed or in the correct location")
        return False


def _patch_find_library(lib_name, lib_path):
    """Patch ctypes.util.find_library function"""
    import ctypes.util

    original_find_library = ctypes.util.find_library

    def patched_find_library(name):
        if name == lib_name:
            return lib_path
        return original_find_library(name)

    ctypes.util.find_library = patched_find_library
