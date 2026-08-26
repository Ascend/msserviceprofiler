# msServiceProfiler Security Statement

## System Security Hardening

You are advised to enable the `address space layout randomization` (ASLR) (level 2) in the system. Run the following command to enable it:

    echo 2 > /proc/sys/kernel/randomize_va_space

## User Account Recommendations

 1. Use the principle of least privilege. For example, prevent other users from writing data by disabling permissions like `666` and `777`.

 2. Before installing or using the tool, ensure the executing user's `umask` is 0027 or stricter. ` Otherwise, you may encounter compilation errors, configuration file read failures, or overly permissive permissions on generated directories and files.

 3. All tools in this repository are designed to run with minimal permissions. For security reasons, do not use `root` or other privileged accounts. Always install and execute tools as a regular user.
 
 4. If a tool depends on CANN, install the CANN package under the same non-privileged user. After running the `source` command, do not modify the environment variables in `set_env.sh`.

## File Permission Control

 1. Ensure that the directory permission is `750`.

 2. When providing input files to the tools, the file owner should match the user running the tool process, and permissions should prevent modification by group or others. By default, tool files written to disk are created restrictive permissions that prevent other users from modifying them. You can adjust these permissions after file creation.

 3. Proper permission control is essential during installation and use. For details, see the following table.

### File Permission Reference

| Type                              | Maximum Permission in Linux|
| ---------------------------------- | ------------------- |
| Home directory                        | 750 (rwxr-x---)   |
| Program files (including scripts and library files)    | 550 (r-xr-x---)   |
| Program file directory                      | 550 (r-xr-x---)   |
| Configuration files                          | 640 (rw-r-----)   |
| Configuration file directory                      | 750 (rwxr-x---)   |
| Log files (recorded or archived)    | 440 (r--r-----)   |
| Log files (being recorded)                | 640 (rw-r-----)   |
| Log file directory                      | 750 (rwxr-x---)   |
| Debug files                         | 640 (rw-r-----)   |
| Debug file directory                     | 750 (rwxr-x---)   |
| Temporary file directory                      | 750 (rwxr-x---)   |
| Maintenance and upgrade file directory                  | 770 (rwxrwx---)   |
| Service data files                      | 640 (rw-r-----)   |
| Service data file directory                  | 750 (rwxr-x---)   |
| Key component, private key, certificate, and ciphertext file directory| 700 (rwx------)    |
| Key components, private keys, certificates, and ciphertext files    | 600 (rw-------)   |
| APIs and script files for encryption and decryption            | 500 (r-x------)   |

## Vulnerability Security Statement

For details, see [MindStudio Vulnerability Handling Mechanism Description](./vulnerability_handling_procedure.md).

## Data Security Statement

The tool reads model weights from disk—typically files you've downloaded from the internet and specified via command-line arguments or configuration files. Using untrusted model weights can introduce unknown security risks. Before passing any model weights to the tool, verify their integrity using methods like SHA256 to ensure they come from a trusted source.

## Build Security Statement

msServiceProfiler can be installed from source. During compilation, third-party dependencies are downloaded, the shell build scripts are executed, and temporary program files and compilation directories are generated. To minimize security risks, you can set appropriate permissions on files in the source directory. During compilation, review and modify build scripts as needed before execution, to ensure the final build artifacts are securely stored.

## Running Security Declaration

If the tool encounters an error, it will exit and print error messages. This is expected behavior. To locate the error cause, you are advised to check the log files, examine the output files from data collection and parsing, and review any console messages for clues.

## Public IP Address Statement

For details about the public network information in the configuration files and scripts within the msServiceProfiler repository, see [Public Network Address](./public_ip_address.md).

## Public APIs

msServiceProfiler is developed in C++ and Python. All public APIs are documented.

The tool is distributed as source code (Python and other scripting languages). Always use the documented public APIs. Avoid calling undocumented internal functions.

## Safe Function Usage

While unsafe functions are not forcibly disabled, you are advised to use their safe variants that explicitly take a buffer length parameter, for example, `memset_s` and `memcpy_s`.

## Communication security hardening

It is advised to run the trace data monitoring tool with TLS enabled. Use the tool in a secure network environment, for example, behind a firewall or within a local area network (LAN). Be mindful of potential communication security risks when using third-party software.

## Communication Matrix

| Code Repository| Function| Source Device| Source IP Address| Source Port| Destination Device| Destination IP Address|Destination Port (Listening)| Protocol| Port Description| Port Configuration| Listening Port Configurable (Yes/No)| Authentication Mode| Encryption Mode| Plane| Version| Exceptions| Remarks|
| ------- | ------- | -------- | ------- | ------- | ------ | ------ | ----- | ---- | ------ | -------- | ------ | -------- | -------- | -------- | -------- | -------- | ----- |
|msserviceprofiler | vLLM server communication| vLLM server started by msServiceProfiler Optimizer| IP address matching the port parameter for the inference service| Fixed port configured based on the customer's requirements on the live network, which corresponds to the --port field during service startup. The default value is 8000.| vLLM client| IP address for vLLM client communication| **8000** (default)| HTTP | Starts the inference service in the customer environment through the CLI. If the customer does not specify the port, the default port 8000 is used. Otherwise, start the vLLM service using the port specified by the customer.| N/A  | Yes| N/A| N/A| Data plane| All| None| None|
