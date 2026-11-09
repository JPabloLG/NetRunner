// Condicionales anidados y cadena larga con ->
TARGET NODE 0xFF00 {
    IF ICE_LEVEL < 5 THEN {
        IF FIREWALL == INACTIVE THEN {
            SCAN PORTS -> CONNECT PORT 8080 -> INJECT PAYLOAD "x" -> EXFIL DATA;
        } ELSE {
            BYPASS FIREWALL;
        }
    } ELSE {
        DISABLE FIREWALL;
    }
}
