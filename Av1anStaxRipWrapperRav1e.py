import argparse
import subprocess
import sys

# Functions
def add_argument(curr, new):
    return_string = curr
    if curr == "":
        return_string = new
    else:
        return_string += (" " + new)
    return return_string

def set_path(path):
    import os
    import pathlib
    staxrip_path = pathlib.Path(path)
    av1an_path = staxrip_path / "Apps" / "Encoders" / "av1an"
    ffmpeg_path = staxrip_path / "Apps" / "Encoders" / "ffmpeg"
    rav1e_path = staxrip_path / "Apps" / "Encoders" / "rav1e"
    vp_path = staxrip_path / "Apps" / "FrameServer" / "VapourSynth"
    environ = os.environ
    environ["PATH"] = f"{str(av1an_path)};{str(ffmpeg_path)};{str(rav1e_path)};{str(vp_path)};{environ['PATH']}"
    return environ

def print_version(parser_args):
    if parser_args.staxrip_startup_dir is not None:
        my_env = set_path(parser_args.staxrip_startup_dir)
        subprocess.run("av1an --version", shell=False, env=my_env) # Assume everything is in PATH
        print("")
        subprocess.run("rav1e --version", shell=False, env=my_env)
    else:
        subprocess.run("av1an --version", shell=False) # Assume everything is in PATH
        print("")
        subprocess.run("rav1e --version", shell=False)
    exit(0)

# Command Line Arguments
parser = argparse.ArgumentParser(description="Av1an wrapper for StaxRip")

parser.add_argument('-i', dest="input", type=str, help="Input File (for StaxRip)")
parser.add_argument('-o', dest="output", type=str, help="Output File (for StaxRip)")
parser.add_argument('-t', dest="tempdir", type=str, help="Temp Directory (for StaxRip)")
parser.add_argument('-s', '--staxrip-startup-dir', dest="staxrip_startup_dir", type=str, required=False, help="Specify StaxRip Startup Directory so that the wrapper script will automatically add important folders to PATH for av1an to detect (only needed for portable installations)")
parser.add_argument('--version', action='store_true', help="Print Av1an and rav1e versions")
parser.add_argument('--photon-noise', dest="photon_noise", type=str, required=False, help="Generates a photon noise table and applies it using grain synthesis [strength: 0-64] (disabled by default) (Av1an parameter)")
parser.add_argument('--chroma-noise', dest="chroma_noise", action='store_true', help="Adds chroma grain synthesis to the grain table generated by `--photon-noise`. (Default: false) (Av1an parameter)")
parser.add_argument('--sc-downscale-height', dest="sc_downscale_height", type=str, required=False, help="Optional downscaling for scene detection. By default, no downscaling is performed. (Av1an parameter)")
# Threading Arguments (do not specify these commands if you want to use Automatic Thread Detection)
parser.add_argument('--workers', type=str, required=False, help="Number of workers to spawn [0 = automatic] (Av1an Paramter)")
parser.add_argument('--set-thread-affinity', dest="set_thread_affinity", type=str, required=False, help="Pin each worker to a specific set of threads of this size (disabled by default) (Av1an parameter)")
parser.add_argument('--disable-automatic-thread-detection', dest="disable_automatic_thread_detection", action='store_true', help="Disable the wrapper's automatic thread detection")
# Rav1e arguments
parser.add_argument('--quantizer', type=str, required=False, help="Quantizer (0-255), smaller values are higher quality (default: 100) (rav1e parameter)") # Quantizer (0-255), smaller values are higher quality (default: 100)
parser.add_argument('--speed', type=str, required=False, help="Speed level (0 is best quality, 10 is fastest)\nSpeeds 10 and 0 are extremes and are generally not recommended\n[default: 6] (rav1e parameter)") # Speed level 0-10 (0 is best quality, 10 is fastest) (default: 6)
parser.add_argument('--tiles', type=str, required=False, help="Number of tiles. Tile-cols and tile-rows are overridden so that the video has at least this many tiles (rav1e parameter)")
parser.add_argument('--threads', type=str, required=False, help="Set the threadpool size. If 0, will use the number of logical CPUs. rav1e will use up to this many threads.\nAdditional tiles may be needed to increase thread utilization\n[default: 0] (rav1e parameter)")
parser_args = parser.parse_args()

if parser_args.version:
    print_version(parser_args)

if parser_args.input is None or parser_args.output is None or parser_args.tempdir is None:
    print("The arguments, -i, -o, -t are required to work!")
    exit(1)

input_file = parser_args.input
output_file = parser_args.output
tempdir = parser_args.tempdir

# # Parsing rav1e arguments
rav1e_argument_string = ""
    
if parser_args.speed is not None:
    rav1e_argument_string = add_argument(rav1e_argument_string, f"--speed {parser_args.speed}")
if parser_args.quantizer is not None:
    rav1e_argument_string = add_argument(rav1e_argument_string, f"--quantizer {parser_args.quantizer}")
if parser_args.tiles is not None:
    rav1e_argument_string = add_argument(rav1e_argument_string, f"--tiles {parser_args.tiles}")
if parser_args.threads is not None:
    rav1e_argument_string = add_argument(rav1e_argument_string, f"--threads {parser_args.threads}")

# Automatic Thread Detection
thread_detection = False
if not parser_args.disable_automatic_thread_detection and parser_args.workers is None and parser_args.set_thread_affinity is None:
    thread_detection = True

if thread_detection: # Checking for new Intel architecture
    import psutil
    logical_count = psutil.cpu_count(logical = True)
    physical_count = psutil.cpu_count(logical = False)
    if (logical_count / physical_count) % 1 != 0:
        thread_detection = False  # Intel CPU detected
        print("New Intel CPU architecture with performance and efficiency cores detected!\nNot passing thread detection to av1an...\n")
    
if thread_detection: # Checking for Hyperthreading or SMT
    import psutil
    logical_count = psutil.cpu_count(logical = True)
    physical_count = psutil.cpu_count(logical = False)
    if (logical_count / physical_count) == 2:
        hyperthreading = True
    else:
        hyperthreading = False
        
if thread_detection: # Setting values
    if hyperthreading:
        cpu_workers = physical_count
        cpu_thread_affinity = 2
    else:
        cpu_workers = physical_count
        cpu_thread_affinity = 1
    print(f"THREADING INFORMATION:\n  Hyperthreading / SMT: {hyperthreading}\n  Workers: {cpu_workers}\n  Thread Affinity: {cpu_thread_affinity}\n\n")
else:
    print("THREADING INFORMATION:\n  Automatic Thread Detection: DISABLED\n\n")

# If StaxRip path given, automatically add important folders to PATH
if parser_args.staxrip_startup_dir is not None:
    my_env = set_path(parser_args.staxrip_startup_dir)

av1an_exec = "av1an.exe"

command = av1an_exec
command = add_argument(command, "--verbose -y --resume -a=\"-an\" -e rav1e --pix-format yuv420p10le")

# Thread arguments
if thread_detection:
    command = add_argument(command, f"--workers {cpu_workers} --set-thread-affinity {cpu_thread_affinity}")
else:
    if parser_args.workers is not None:
        command = add_argument(command, f"--workers {parser_args.workers}")
    if parser_args.set_thread_affinity is not None:
        command = add_argument(command, f"--set-thread-affinity {parser_args.set_thread_affinity}")

if parser_args.photon_noise is not None:
    command = add_argument(command, f"--photon-noise {parser_args.photon_noise}")
if parser_args.chroma_noise:
    command = add_argument(command, f"--chroma-noise")
if parser_args.sc_downscale_height is not None:
    command = add_argument(command, f"--sc-downscale-height {parser_args.sc_downscale_height}")

if rav1e_argument_string != "":
    command = add_argument(command, f"-v=\"{rav1e_argument_string} --no-scene-detection\"")

command = add_argument(command, f"-i \"{input_file}\" -o \"{output_file}\" --temp \"{tempdir}\"")
       
sys.stdout.write("Starting av1an... Check new console window for progress\n")
sys.stdout.write("Command: " + str(command) + "\n")
sys.stdout.flush()

if parser_args.staxrip_startup_dir is not None:
    process = subprocess.run(command, shell=False, creationflags=subprocess.CREATE_NEW_CONSOLE, env=my_env)
else:
    process = subprocess.run(command, shell=False, creationflags=subprocess.CREATE_NEW_CONSOLE) # Assume everything is in PATH

if process.returncode != 0:
    print(process.stderr)
    print("Error occurred when transcoding with av1an. Check logs")
    exit(1)
