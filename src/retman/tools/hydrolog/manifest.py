"""Hydrolog operation manifest: hydrological computations (ADR-001, ADR-004).

The operations run the commands of Hydrolog's catalog that the Nogat registry routes
to Hydrolog. Those whose inputs a Polish sentence states (a curve number, a rainfall,
an area, durations) take numbers read by the extractors of numbers with units; those
that need a document take it as an input of the plan: a watershed file
(``WatershedParameters.to_json()``) or the daily flow series of an Obserwator export.
"""

from retman.registry.manifest import InputSpec, ManifestSpec, ParamSpec

_CALLS = "retman.tools.hydrolog.calls"
_DESCRIBE = "retman.tools.hydrolog.describe"
_PREVIEW = "retman.tools.hydrolog.preview"

_CURVE_NUMBER: ParamSpec = {
    "name": "cn",
    "type": "free",
    "extractor": "curve_number",
    "required": True,
}
_RAINFALL: ParamSpec = {
    "name": "rainfall",
    "type": "free",
    "extractor": "rainfall_depth",
    "required": True,
}
# The antecedent moisture condition: the CN tables are for AMC II, which is also
# Hydrolog's default; a command that names dry or wet conditions picks another
_AMC: ParamSpec = {
    "name": "amc",
    "type": "choice",
    "options": ["dry", "normal", "wet"],
    "tool_values": {"dry": "I", "normal": "II", "wet": "III"},
    "default": "normal",
}
# The design rainfall: its shape is required by Hydrolog, the time step has the tool's
# own default of 5 minutes, shown in the plan as a default
_HYETOGRAPH: ParamSpec = {
    "name": "hyetograph",
    "type": "choice",
    "options": ["block", "triangular", "beta", "euler_ii"],
    "required": True,
}
_DURATION: ParamSpec = {
    "name": "duration",
    "type": "free",
    "extractor": "rain_duration",
    "required": True,
}
_TIME_STEP: ParamSpec = {
    "name": "time_step",
    "type": "free",
    "extractor": "time_step",
    "default": 5,
}
_WATERSHED: InputSpec = {"name": "watershed", "kind": "watershed_parameters"}

MANIFEST: ManifestSpec = {
    "tool": "hydrolog",
    "distribution": "hydrolog",
    "source": "git+https://github.com/Daldek/Hydrolog",
    "supported_versions": ">=1.0.0.dev0,<2",
    "translations": {"pl": "pl.toml", "en": "en.toml"},
    "client": "retman.tools.hydrolog.client:create",
    "operations": [
        {
            "id": "compute_concentration_time",
            "category": "rainfall_runoff",
            "description": "Compute the time of concentration of a watershed file by "
            "a chosen method",
            "inputs": [_WATERSHED],
            "outputs": ["hydrolog_report"],
            "commands": ["tc watershed"],
            "calls": f"{_CALLS}:compute_concentration_time",
            "describe": f"{_DESCRIBE}:compute_concentration_time",
            "preview": f"{_PREVIEW}:compute_concentration_time",
            "params": [
                {
                    # Methods differ by a factor of two and more: never a default
                    "name": "method",
                    "type": "choice",
                    "options": [
                        "kirpich",
                        "nrcs",
                        "giandotti",
                        "faa",
                        "kerby",
                        "kerby_kirpich",
                    ],
                    "required": True,
                },
            ],
        },
        {
            "id": "compute_effective_rainfall",
            "category": "rainfall_runoff",
            "description": "Compute the effective rainfall of a total by SCS-CN",
            "inputs": [],
            "outputs": ["hydrolog_report"],
            "commands": ["scs effective"],
            "calls": f"{_CALLS}:compute_effective_rainfall",
            "describe": f"{_DESCRIBE}:compute_effective_rainfall",
            "preview": f"{_PREVIEW}:compute_effective_rainfall",
            "params": [_CURVE_NUMBER, _RAINFALL, _AMC],
        },
        {
            "id": "build_design_hyetograph",
            "category": "rainfall_runoff",
            "description": "Build a design hyetograph: block, triangular, Beta or "
            "Euler type II",
            "inputs": [],
            "outputs": ["hydrolog_report"],
            "commands": ["precip hietogram"],
            "calls": f"{_CALLS}:build_design_hyetograph",
            "describe": f"{_DESCRIBE}:build_design_hyetograph",
            "preview": f"{_PREVIEW}:build_design_hyetograph",
            "params": [_HYETOGRAPH, _RAINFALL, _DURATION, _TIME_STEP],
        },
        {
            "id": "generate_design_hydrograph",
            "category": "rainfall_runoff",
            "description": "Compute the design direct-runoff hydrograph of a "
            "catchment from its area, CN and time of concentration",
            "inputs": [],
            "outputs": ["hydrolog_report"],
            "commands": ["hydrograph generate"],
            "calls": f"{_CALLS}:generate_design_hydrograph",
            "describe": f"{_DESCRIBE}:generate_design_hydrograph",
            "preview": f"{_PREVIEW}:generate_design_hydrograph",
            "params": [
                {
                    "name": "catchment_area",
                    "type": "free",
                    "extractor": "catchment_area",
                    "required": True,
                },
                _CURVE_NUMBER,
                {
                    "name": "concentration_time",
                    "type": "free",
                    "extractor": "concentration_time",
                    "required": True,
                },
                _HYETOGRAPH,
                _RAINFALL,
                _DURATION,
                _TIME_STEP,
                _AMC,
            ],
        },
        {
            "id": "estimate_flood_quantiles",
            "category": "hydrology_analysis",
            "description": "Compute flood quantiles from the daily flows of an "
            "Obserwator series export",
            "inputs": [{"name": "series", "kind": "hydro_series"}],
            "outputs": ["hydrolog_report"],
            "commands": ["stats flood-frequency"],
            "calls": f"{_CALLS}:estimate_flood_quantiles",
            "describe": f"{_DESCRIBE}:estimate_flood_quantiles",
            "preview": f"{_PREVIEW}:estimate_flood_quantiles",
            "params": [
                {
                    "name": "distribution",
                    "type": "choice",
                    "options": ["all", "log_normal", "gev", "pearson3", "weibull"],
                    "default": "all",
                },
                {
                    # Exceedance probabilities; Hydrolog takes their return periods
                    "name": "probability",
                    "type": "free",
                    "extractor": "probability",
                    "multiple": True,
                },
            ],
        },
        {
            "id": "compute_watershed_morphometry",
            "category": "hydrology_analysis",
            "description": "Compute the geometric, shape and relief indicators of a "
            "watershed file",
            "inputs": [_WATERSHED],
            "outputs": ["hydrolog_report"],
            "commands": ["morphometry watershed"],
            "calls": f"{_CALLS}:compute_watershed_morphometry",
            "describe": f"{_DESCRIBE}:compute_watershed_morphometry",
            "preview": f"{_PREVIEW}:compute_watershed_morphometry",
            "params": [],
        },
    ],
}
