import random
import sys

def generate_stress_ng_jobs(cpu_range, io_range, vm_range, vm_bytes_range, timeout_range, num_jobs, file_path):
    # Open the file in append mode
    total_num = num_jobs
    with open(file_path, 'a') as file:
        while num_jobs != 0:
            # Randomly select values from the ranges
            cpu_count = random.randint(*cpu_range)
            io_count = random.randint(*io_range)
            vm_count = random.randint(*vm_range)
            vm_bytes = f"{random.randint(*vm_bytes_range)}G"
            timeout = f"{random.randint(*timeout_range)}s"

            # Format the stress-ng command
            command = "stress-ng"
            if cpu_count != 0:
                command += f" -- cpu {cpu_count}"
            if io_count != 0:
                command += f" --io {io_count}"
            if vm_count != 0 and vm_bytes != "0G":
                command += f" --vm {vm_count} --vm-bytes {vm_bytes}"
            elif vm_count != 0 or vm_bytes != "0G":
                continue  # Skip this job if only one of vm or vm_bytes is set
            if command == "stress-ng":
                # ignore empty commands
                continue
            if timeout != "0s":
                command += f" --timeout {timeout}"
            
            # Append the command to the file
            file.write(command + "\n")
            num_jobs -= 1

    return f"Generated {total_num} stress-ng jobs and appended to {file_path}"

if __name__ == "__main__":
    # Read arguments from the command line
    # python3 Job_Queue/job_generation.py 0 5 0 5 0 4 10 30 30
    try:
        # io_range = (int(sys.argv[1]), int(sys.argv[2]))
        # vm_range = (int(sys.argv[3]), int(sys.argv[4]))
        # vm_bytes_range = (int(sys.argv[5]), int(sys.argv[6]))  # in GB
        # timeout_range = (int(sys.argv[7]), int(sys.argv[8]))  # in minutes
        # num_of_jobs = int(sys.argv[9])
        cpu_range = (1,3)
        io_range = (1,3)
        vm_range = (1,3)
        vm_bytes_range = (1,2)
        timeout_range = (60,180)
        num_of_jobs = 30
    except IndexError:
        print("Error: Not enough arguments provided.")
        sys.exit(1)
    except ValueError:
        print("Error: Invalid argument type. Please provide integer values.")
        sys.exit(1)

    # Set a default output file path
    output_file_path = "job_list.txt"

    result = generate_stress_ng_jobs(cpu_range, io_range, vm_range, vm_bytes_range, timeout_range, num_of_jobs, output_file_path)
    print(result)
