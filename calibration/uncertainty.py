import math
from typing import Dict, List, Tuple, Optional
from abc import ABC, abstractmethod
import logging
from config import (REFERENCE_UNCERTAINTY, RESOLUTION_UNCERTAINTY,
                    STABILITY_UNCERTAINTY, HOMOGENEITY_UNCERTAINTY,
                    DRIFT_UNCERTAINTY, PT100_CLASS_AA_TOLERANCE,
                    PT100_CLASS_A_TOLERANCE, PT100_CLASS_B_TOLERANCE,
                    PT100_CLASS_C_TOLERANCE, TC_K_CLASS_1_TOLERANCE,
                    TC_K_CLASS_2_TOLERANCE, TC_S_CLASS_1_TOLERANCE)

logger = logging.getLogger(__name__)


class UncertaintyCalculator(ABC):
    @abstractmethod
    def calculate_type_a(self, std_dev: float, n_measurements: int) -> float:
        pass

    @abstractmethod
    def calculate_type_b(self, temperature: float) -> float:
        pass

    @abstractmethod
    def calculate_combined(self, u_a: float, u_b: float) -> float:
        pass

    @abstractmethod
    def calculate_expanded(self, u_c: float, k: float = 2.0) -> float:
        pass

    @abstractmethod
    def classify_sensor(self, max_error: float, temperature: float) -> str:
        pass


class PT100UncertaintyCalculator(UncertaintyCalculator):
    def __init__(self):
        self.reference_uncertainty = REFERENCE_UNCERTAINTY
        self.resolution_uncertainty = RESOLUTION_UNCERTAINTY
        self.stability_uncertainty = STABILITY_UNCERTAINTY
        self.homogeneity_uncertainty = HOMOGENEITY_UNCERTAINTY
        self.drift_uncertainty = DRIFT_UNCERTAINTY

    def calculate_type_a(self, std_dev: float, n_measurements: int) -> float:
        if n_measurements < 2:
            return 0.0
        return std_dev / math.sqrt(n_measurements)

    def calculate_type_b(self, temperature: float) -> float:
        u_ref = self.reference_uncertainty / math.sqrt(3)
        u_res = self.resolution_uncertainty / math.sqrt(3)
        u_stab = self.stability_uncertainty / math.sqrt(3)
        u_hom = self.homogeneity_uncertainty / math.sqrt(3)
        u_drift = self.drift_uncertainty / math.sqrt(3)
        u_b = math.sqrt(u_ref**2 + u_res**2 + u_stab**2 + u_hom**2 + u_drift**2)
        return u_b

    def calculate_combined(self, u_a: float, u_b: float) -> float:
        return math.sqrt(u_a**2 + u_b**2)

    def calculate_expanded(self, u_c: float, k: float = 2.0) -> float:
        return k * u_c

    def classify_sensor(self, max_error: float, temperature: float) -> str:
        abs_error = abs(max_error)
        if abs_error <= PT100_CLASS_AA_TOLERANCE(temperature):
            return "AA"
        elif abs_error <= PT100_CLASS_A_TOLERANCE(temperature):
            return "A"
        elif abs_error <= PT100_CLASS_B_TOLERANCE(temperature):
            return "B"
        elif abs_error <= PT100_CLASS_C_TOLERANCE(temperature):
            return "C"
        else:
            return "Poza klasą"

    def get_tolerance(self, sensor_class: str, temperature: float) -> float:
        tolerances = {
            "AA": PT100_CLASS_AA_TOLERANCE,
            "A": PT100_CLASS_A_TOLERANCE,
            "B": PT100_CLASS_B_TOLERANCE,
            "C": PT100_CLASS_C_TOLERANCE,
        }
        func = tolerances.get(sensor_class)
        if func:
            return func(temperature)
        return float('inf')


class ThermocoupleUncertaintyCalculator(UncertaintyCalculator):
    def __init__(self, tc_type: str = "K"):
        self.tc_type = tc_type.upper()
        self.reference_uncertainty = REFERENCE_UNCERTAINTY * 2
        self.resolution_uncertainty = RESOLUTION_UNCERTAINTY
        self.stability_uncertainty = STABILITY_UNCERTAINTY
        self.homogeneity_uncertainty = HOMOGENEITY_UNCERTAINTY
        self.drift_uncertainty = DRIFT_UNCERTAINTY * 2
        self.cold_junction_uncertainty = 0.5

    def calculate_type_a(self, std_dev: float, n_measurements: int) -> float:
        if n_measurements < 2:
            return 0.0
        return std_dev / math.sqrt(n_measurements)

    def calculate_type_b(self, temperature: float) -> float:
        u_ref = self.reference_uncertainty / math.sqrt(3)
        u_res = self.resolution_uncertainty / math.sqrt(3)
        u_stab = self.stability_uncertainty / math.sqrt(3)
        u_hom = self.homogeneity_uncertainty / math.sqrt(3)
        u_drift = self.drift_uncertainty / math.sqrt(3)
        u_cj = self.cold_junction_uncertainty / math.sqrt(3)
        u_b = math.sqrt(u_ref**2 + u_res**2 + u_stab**2 + 
                       u_hom**2 + u_drift**2 + u_cj**2)
        return u_b

    def calculate_combined(self, u_a: float, u_b: float) -> float:
        return math.sqrt(u_a**2 + u_b**2)

    def calculate_expanded(self, u_c: float, k: float = 2.0) -> float:
        return k * u_c

    def classify_sensor(self, max_error: float, temperature: float) -> str:
        abs_error = abs(max_error)
        
        if self.tc_type == "K":
            if abs_error <= TC_K_CLASS_1_TOLERANCE(temperature):
                return "Klasa 1"
            elif abs_error <= TC_K_CLASS_2_TOLERANCE(temperature):
                return "Klasa 2"
            else:
                return "Poza klasą"
        elif self.tc_type == "S":
            if abs_error <= TC_S_CLASS_1_TOLERANCE(temperature):
                return "Klasa 1"
            elif abs_error <= TC_S_CLASS_1_TOLERANCE(temperature) * 1.5:
                return "Klasa 2"
            else:
                return "Poza klasą"
        else:
            if abs_error <= max(1.5, 0.004 * abs(temperature)):
                return "Klasa 1"
            elif abs_error <= max(2.5, 0.0075 * abs(temperature)):
                return "Klasa 2"
            else:
                return "Poza klasą"


class UncertaintyBudget:
    def __init__(self):
        self.components: List[Dict] = []

    def add_component(self, name: str, value: float, 
                     distribution: str = "prostokątny",
                     divisor: float = None,
                     sensitivity: float = 1.0):
        if divisor is None:
            divisor = math.sqrt(3) if distribution == "prostokątny" else 1.0
        
        u = value / divisor
        contribution = (sensitivity * u) ** 2
        
        self.components.append({
            "name": name,
            "value": value,
            "distribution": distribution,
            "divisor": divisor,
            "standard_uncertainty": u,
            "sensitivity": sensitivity,
            "contribution": contribution
        })

    def calculate_combined(self) -> float:
        total = sum(c["contribution"] for c in self.components)
        return math.sqrt(total)

    def get_budget_table(self) -> List[Dict]:
        combined = self.calculate_combined()
        table = []
        for c in self.components:
            percentage = (c["contribution"] / (combined**2) * 100) if combined > 0 else 0
            table.append({
                **c,
                "percentage_contribution": percentage
            })
        return table


def create_uncertainty_calculator(sensor_type: str) -> UncertaintyCalculator:
    if sensor_type == "PT100":
        return PT100UncertaintyCalculator()
    elif sensor_type.startswith("TC_"):
        tc_type = sensor_type.split("_")[1] if "_" in sensor_type else "K"
        return ThermocoupleUncertaintyCalculator(tc_type)
    else:
        return PT100UncertaintyCalculator()


def calculate_full_uncertainty(std_dev: float, n_measurements: int,
                               temperature: float, sensor_type: str = "PT100",
                               k: float = 2.0) -> Dict:
    calculator = create_uncertainty_calculator(sensor_type)
    
    u_a = calculator.calculate_type_a(std_dev, n_measurements)
    u_b = calculator.calculate_type_b(temperature)
    u_c = calculator.calculate_combined(u_a, u_b)
    u_expanded = calculator.calculate_expanded(u_c, k)
    
    return {
        "type_a": u_a,
        "type_b": u_b,
        "combined": u_c,
        "expanded": u_expanded,
        "coverage_factor": k,
        "effective_dof": n_measurements - 1 if n_measurements > 1 else 1
    }