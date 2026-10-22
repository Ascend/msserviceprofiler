# Macro Definition <a name="EN-US_TOPIC_0000002184676765"></a>

- `PROF`: encapsulates profiling statements. Use the `ENABLE\_PROF` macro to control whether profiling is enabled during compilation. `PROF` supports one or two parameters.
    - One parameter: profiling statement.

        If `ENABLE\_PROF` is defined, the `print` statement is executed. If it is not defined, printing is skipped.

        PROF\(std::cout**<<**  "enable prof"  **<<**  std::endl\);

    - Two parameters: profiling level and profiling statement. Automatically initializes the `Profiler` class and defines the profiling level.

        If `ENABLE\_PROF` is defined, profiling is executed. If it is not defined, no profiling occurs. The `Profiler` class is automatically initialized.

        PROF\(INFO, Attr\("req", 1\).Event\("recv"\)\);

- `ENABLE\_PROF`: works with `PROF`. If this environment variable is not defined, profiling is disabled, and `PROF` is automatically defined as empty. Generally, it is defined in `CMakeLists.txt`.

    add\_definitions\(-DENABLE\_PROF\)
