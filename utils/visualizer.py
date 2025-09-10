# utils/visualizer.py
import os

import matplotlib.pyplot as plt


def visualize_dcf_time_series(dcf_list: list[dict], symbol: str, save_path: str):
    try:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # 📅 데이터 준비
        years = []
        equity_values = []
        waccs = []
        terminal_values = []

        for item in sorted(dcf_list, key=lambda x: x.get("year", "0000")):
            year = str(item.get("year"))
            if not year:
                continue
            ev = item.get("equityValuePerShare", 0)
            wacc = item.get("wacc", 0)
            terminal = item.get("terminalValue", 0)

            years.append(year)
            equity_values.append(ev or 0)
            waccs.append(wacc or 0)
            terminal_values.append(terminal or 0)

        if not years:
            return

        # 📊 시각화
        plt.figure(figsize=(10, 6))
        plt.rcParams['font.family'] = 'Malgun Gothic'  # 한글 폰트 (Windows 기준)
        plt.rcParams['axes.unicode_minus'] = False  # 마이너스 깨짐 방지
        ax1 = plt.gca()
        ax1.set_title(f"{symbol} DCF 시계열", fontsize=14)

        ax1.plot(years, equity_values, label="Equity/Share ($)", marker='o', color='blue')
        ax1.plot(years, terminal_values, label="Terminal Value", marker='s', linestyle='--', color='green')
        ax1.set_ylabel("가치 ($)")
        ax1.grid(True, linestyle="--", alpha=0.5)

        ax2 = ax1.twinx()
        ax2.plot(years, waccs, label="WACC (%)", marker='x', color='gray')
        ax2.set_ylabel("WACC (%)")

        # 🎯 범례 통합
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

        plt.tight_layout()
        plt.savefig(save_path)
        plt.close()

    except Exception as e:
        raise RuntimeError(f"DCF 시각화 실패 ({symbol}): {e}")
