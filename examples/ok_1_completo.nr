// Simulación: reconocimiento, acceso y limpieza
TARGET NODE 0xad23d {
    SCAN PORTS;
    SCAN PORTS -> CONNECT PORT 22;

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
