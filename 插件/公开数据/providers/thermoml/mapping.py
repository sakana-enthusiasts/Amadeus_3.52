THERMOML_PROPERTY_MAP = {
    "Mass density, kg/m3": ("density", "kg/m3"), "Density, kg/m3": ("density", "kg/m3"),
    "Viscosity, Pa*s": ("viscosity", "Pa s"), "Surface tension liquid-gas, N/m": ("surface_tension", "N/m"),
    "Refractive index (Na D-line)": ("refractive_index", "1"),
    "Refractive index (other wavelength)": ("refractive_index", "1"),
    "Vapor or sublimation pressure, kPa": ("vapor_pressure", "kPa"),
    "Normal boiling temperature, K": ("boiling_point", "K"), "Normal melting temperature, K": ("melting_point", "K"),
    "Molar heat capacity at constant pressure, J/K/mol": ("heat_capacity", "J/K/mol"),
}
THERMOML_CONDITION_MAP = {
    "Temperature, K": ("temperature", "K"), "Pressure, kPa": ("pressure", "kPa"),
    "Wavelength, nm": ("wavelength", "nm"), "pH": ("pH", "1"),
}
