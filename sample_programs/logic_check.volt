20v ===> [-32v+] ===> || sensor_voltage ;
sensor_voltage ===> (>) 10v ===> [+8v-] ===> || is_triggered ;
_/_[is_triggered] {
    [^]: "Warning: High Voltage" ===> (O) ===> _|_ ;
    [v]: "Voltage Normal" ===> (O) ===> _|_ ;
}
sensor_voltage ===> _|_ ;
is_triggered ===> _|_ ;
