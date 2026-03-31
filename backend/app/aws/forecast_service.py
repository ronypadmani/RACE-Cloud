"""
Forecast Service — predicts future AWS costs and detects spending anomalies.
Uses simple linear regression and threshold-based anomaly detection.
No heavy ML libraries — pure Python math only. Read-only operations.
"""
from typing import List


class ForecastService:
    """Cost forecasting and anomaly detection using historical cost data."""

    def __init__(self, daily_costs: list, monthly_costs: list = None):
        """
        Args:
            daily_costs: List of {'date': str, 'cost': float} from CostService.
            monthly_costs: List of monthly cost dicts from CostService (optional).
        """
        self._daily = daily_costs or []
        self._monthly = monthly_costs or []

    # ── Cost Prediction ────────────────────────────────────────────────────────

    def get_cost_prediction(self, forecast_days: int = 30) -> dict:
        """
        Predict next N days cost using linear regression on daily spend.
        Falls back to moving average if insufficient data for regression.
        """
        costs = [d['cost'] for d in self._daily if isinstance(d.get('cost'), (int, float))]

        if not costs:
            return {
                'predicted_monthly_cost': 0.0,
                'method': 'none',
                'confidence': 'low',
                'data_points': 0,
                'daily_average': 0.0,
                'trend': 'stable',
            }

        n = len(costs)
        daily_avg = sum(costs) / n

        if n >= 7:
            # Linear regression: y = mx + b
            x_vals = list(range(n))
            x_mean = sum(x_vals) / n
            y_mean = daily_avg

            numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, costs))
            denominator = sum((x - x_mean) ** 2 for x in x_vals)

            if denominator != 0:
                slope = numerator / denominator
                intercept = y_mean - slope * x_mean

                # Predict costs for each future day
                predicted_daily = []
                for i in range(forecast_days):
                    future_x = n + i
                    pred = max(slope * future_x + intercept, 0)
                    predicted_daily.append(round(pred, 4))

                predicted_total = sum(predicted_daily)
                method = 'linear_regression'

                # Determine trend
                if slope > 0.5:
                    trend = 'increasing'
                elif slope < -0.5:
                    trend = 'decreasing'
                else:
                    trend = 'stable'

                # Confidence based on data points and R² approximation
                ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_vals, costs))
                ss_tot = sum((y - y_mean) ** 2 for y in costs)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

                if n >= 20 and r_squared > 0.5:
                    confidence = 'high'
                elif n >= 10:
                    confidence = 'medium'
                else:
                    confidence = 'low'

                return {
                    'predicted_monthly_cost': round(predicted_total, 2),
                    'predicted_daily_avg': round(predicted_total / forecast_days, 2),
                    'method': method,
                    'confidence': confidence,
                    'data_points': n,
                    'daily_average': round(daily_avg, 4),
                    'trend': trend,
                    'slope': round(slope, 4),
                    'r_squared': round(r_squared, 4),
                    'forecast_days': forecast_days,
                    'predicted_daily': predicted_daily,
                }

        # Fallback: moving average
        window = min(7, n)
        recent_avg = sum(costs[-window:]) / window
        predicted_total = recent_avg * forecast_days

        return {
            'predicted_monthly_cost': round(predicted_total, 2),
            'predicted_daily_avg': round(recent_avg, 2),
            'method': 'moving_average',
            'confidence': 'low',
            'data_points': n,
            'daily_average': round(daily_avg, 4),
            'trend': 'stable',
            'forecast_days': forecast_days,
        }

    # ── Anomaly Detection ──────────────────────────────────────────────────────

    def detect_anomalies(self, sensitivity: float = 2.0) -> dict:
        """
        Detect cost anomalies using standard deviation thresholds.
        A day is anomalous if its cost exceeds mean + sensitivity * std_dev.

        Args:
            sensitivity: Number of standard deviations above mean to flag.
                         2.0 = moderate, 1.5 = aggressive, 3.0 = conservative.
        """
        costs = [d['cost'] for d in self._daily if isinstance(d.get('cost'), (int, float))]
        dates = [d['date'] for d in self._daily if isinstance(d.get('cost'), (int, float))]

        if len(costs) < 3:
            return {
                'anomalies': [],
                'threshold': 0,
                'mean': 0,
                'std_dev': 0,
                'data_points': len(costs),
            }

        n = len(costs)
        mean = sum(costs) / n
        variance = sum((c - mean) ** 2 for c in costs) / n
        std_dev = variance ** 0.5
        threshold = mean + sensitivity * std_dev

        anomalies = []
        for date, cost in zip(dates, costs):
            if cost > threshold and cost > 0.01:
                deviation = ((cost - mean) / std_dev) if std_dev > 0 else 0
                anomalies.append({
                    'date': date,
                    'cost': round(cost, 4),
                    'expected': round(mean, 4),
                    'deviation': round(deviation, 2),
                    'severity': 'HIGH' if deviation > 3 else 'MEDIUM' if deviation > 2 else 'LOW',
                })

        return {
            'anomalies': sorted(anomalies, key=lambda a: a['cost'], reverse=True),
            'anomaly_count': len(anomalies),
            'threshold': round(threshold, 4),
            'mean': round(mean, 4),
            'std_dev': round(std_dev, 4),
            'sensitivity': sensitivity,
            'data_points': n,
            'daily_costs_with_threshold': [
                {
                    'date': d,
                    'cost': round(c, 4),
                    'threshold': round(threshold, 4),
                    'is_anomaly': c > threshold and c > 0.01,
                }
                for d, c in zip(dates, costs)
            ],
        }

    # ── Budget Comparison ──────────────────────────────────────────────────────

    @staticmethod
    def compare_budget(predicted_cost: float, monthly_limit: float) -> dict:
        """
        Compare predicted cost against user's budget limit.
        Returns status, percentage, and alert level.
        """
        if monthly_limit <= 0:
            return {
                'status': 'no_budget',
                'message': 'No budget limit set.',
                'percentage': 0,
                'alert_level': 'NONE',
            }

        percentage = (predicted_cost / monthly_limit) * 100
        remaining = monthly_limit - predicted_cost

        if percentage >= 100:
            alert_level = 'HIGH'
            status = 'over_budget'
            message = f'Predicted cost ${predicted_cost:.2f} EXCEEDS budget ${monthly_limit:.2f} by ${abs(remaining):.2f}'
        elif percentage >= 80:
            alert_level = 'MEDIUM'
            status = 'warning'
            message = f'Predicted cost is {percentage:.0f}% of budget. ${remaining:.2f} remaining.'
        elif percentage >= 60:
            alert_level = 'LOW'
            status = 'caution'
            message = f'Predicted cost is {percentage:.0f}% of budget. On track.'
        else:
            alert_level = 'NONE'
            status = 'on_track'
            message = f'Predicted cost is {percentage:.0f}% of budget. Well within limits.'

        return {
            'status': status,
            'message': message,
            'predicted_cost': round(predicted_cost, 2),
            'monthly_limit': round(monthly_limit, 2),
            'remaining': round(remaining, 2),
            'percentage': round(percentage, 1),
            'alert_level': alert_level,
        }
