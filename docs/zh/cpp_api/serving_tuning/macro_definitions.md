# 宏定义<a name="ZH-CN_TOPIC_0000002184676765"></a>

- PROF：将采集语句封装起来，这样可以通过ENABLE\_PROF宏定义在编译期间控制是否采集数据，支持传入一个参数或者两个参数。
    - 一个参数：采集语句。

        当定义ENABLE\_PROF会正常执行打印，当没有定义则不会打印。

        PROF\(std::cout<<  "enable prof"  <<  std::endl\);

    - 两个参数：采集级别，采集语句。自动初始化Profiler类以及定义采集级别。

        当定义ENABLE\_PROF会正常执行采集，当没有定义则不会采集，会自动初始化Profiler类。

        PROF\(INFO, Attr\("req", 1\).Event\("recv"\)\);

- ENABLE\_PROF：与PROF协同使用，当没有定义该宏，说明不开启采集能力，会自动将PROF定义为空实现。通常定义在CMakeLists.txt中。

    add\_definitions\(-DENABLE\_PROF\)
