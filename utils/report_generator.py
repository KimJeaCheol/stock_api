import logging
import os
import traceback
from datetime import datetime

from fpdf import FPDF

logger = logging.getLogger(__name__)

class PDFReport(FPDF):
    def header(self):
        self.add_font('NotoSans', '', 'fonts/NotoSans-Regular.ttf', uni=True)
        self.set_font('NotoSans', '', 14)
        self.cell(0, 10, '📊 Investment Report', ln=True, align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('NotoSans', '', 8)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

    def add_portfolio_summary(self, total_investment, total_value, total_return):
        try:
            logger.info("🧾 포트폴리오 요약 추가 시작")
            self.set_font('NotoSans', '', 12)
            self.cell(0, 10, f'Total Investment: ${total_investment:,.2f}', ln=True)
            self.cell(0, 10, f'Current Value: ${total_value:,.2f}', ln=True)
            self.cell(0, 10, f'Total Return: {total_return:.2f}%', ln=True)
            self.ln(10)
            logger.info("✅ 포트폴리오 요약 추가 완료")
        except Exception as e:
            logger.error(f"❌ 포트폴리오 요약 추가 실패: {e}\n{traceback.format_exc()}")
            raise

    def add_stock_details(self, stock_data):
        try:
            logger.info(f"🧾 종목 상세 추가 시작: {stock_data.get('symbol')}")
            self.set_font('NotoSans', '', 12)
            self.cell(0, 10, f"🔹 {stock_data['symbol']}", ln=True)
            self.set_font('NotoSans', '', 11)
            self.cell(0, 8, f"Current Price: ${stock_data['current_price']}", ln=True)
            self.cell(0, 8, f"Target Allocation: {stock_data['target_allocation']}%", ln=True)
            self.cell(0, 8, f"Current Allocation: {stock_data['current_allocation']:.2f}%", ln=True)
            self.cell(0, 8, f"Recommendation: {stock_data['recommendation']}", ln=True)
            self.ln(5)

            # DCF 차트 삽입
            if 'dcf_chart_path' in stock_data and stock_data['dcf_chart_path']:
                if os.path.exists(stock_data['dcf_chart_path']):
                    self.image(stock_data['dcf_chart_path'], w=150)
                    self.ln(10)
                else:
                    logger.warning(f"⚠️ DCF 차트 파일 없음: {stock_data['dcf_chart_path']}")

            # GPT 요약
            self.set_font('NotoSans', '', 10)
            gpt_summary = stock_data.get('gpt_summary', '요약 없음')
            self.multi_cell(0, 7, f"📝 GPT Summary:\n{gpt_summary}")
            self.ln(10)
            logger.info(f"✅ 종목 상세 추가 완료: {stock_data.get('symbol')}")
        except Exception as e:
            logger.error(f"❌ 종목 상세 추가 실패: {e}\n{traceback.format_exc()}")
            raise

    def add_economic_summary(self, economic_data):
        try:
            logger.info("🧾 경제지표 요약 추가 시작")
            self.set_font('NotoSans', '', 12)
            self.cell(0, 10, "🌍 Economic Indicators", ln=True)
            self.set_font('NotoSans', '', 11)
            for key, value in economic_data.items():
                self.cell(0, 8, f"{key}: {value}", ln=True)
            self.ln(10)
            logger.info("✅ 경제지표 요약 추가 완료")
        except Exception as e:
            logger.error(f"❌ 경제지표 요약 추가 실패: {e}\n{traceback.format_exc()}")
            raise

def generate_investment_report(
    stock_recommendations,
    portfolio_rebalancing,
    portfolio_summary,
    economic_summary,
    output_path
):
    try:
        logger.info("📄 투자 리포트 생성 시작")
        pdf = PDFReport()
        pdf.add_page()

        # 포트폴리오 요약
        pdf.add_portfolio_summary(**portfolio_summary)

        # 종목 추천 리스트 (신규 추천)
        for stock in stock_recommendations:
            pdf.add_stock_details(stock)

        # 포트폴리오 리밸런싱
        for stock in portfolio_rebalancing:
            pdf.add_stock_details(stock)

        # 경제지표 요약
        pdf.add_economic_summary(economic_summary)

        # 저장
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        pdf.output(output_path)
        logger.info(f"✅ 리포트 파일 저장 완료: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"❌ 리포트 생성 중 오류: {e}\n{traceback.format_exc()}")
        raise