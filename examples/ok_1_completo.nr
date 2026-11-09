// Simulación: reconocimiento, acceso y limpieza
TARGET NODE 0xad23d {
    SCAN PORTS;
    SCAN PORT 22 -> CONNECT PORT 22;

    IF FIREWALL == ACTIVE THEN {
        BYPASS FIREWALL;
    } ELSE {
        INJECT PAYLOAD "reverse_shell";
    }

    IF ICE_LEVEL > 3 THEN {
        DISABLE FIREWALL;
        EXECUTE SCRIPT "escalar.sh";
    }

    EXFIL DATA;
    CLEAR LOGS;
}

TARGET NODE 0x1f4 {
    SCAN PORT 80 -> EXFIL DATA;
}
