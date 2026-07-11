WARNING_LEVELS = {0: "Normal", 1: "Warning", 2: "Derating", 3: "Fault", 4: "Severe", 5: "Reserved", 6: "Reserved", 7: "Reserved"}
CHARGE_STATE = {0: "idle", 1: "charging", 2: "discharging", 3: "reserved"}
BMS_IDS = set(range(0x100, 0x10A))
CONTROL_ID = 0x121
DISABLED_CONTROL_IDS = {0x123, 0x126, 0x710, 0x715}
