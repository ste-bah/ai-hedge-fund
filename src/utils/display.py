from colorama import Fore, Style
from tabulate import tabulate
from .analysts import ANALYST_ORDER
import os
import json
from fpdf import FPDF # Import FPDF
from datetime import datetime # Import datetime
import textwrap # Already imported, but good to note


def sort_agent_signals(signals):
    """Sort agent signals in a consistent order."""
    # Create order mapping from ANALYST_ORDER
    analyst_order = {display: idx for idx, (display, _) in enumerate(ANALYST_ORDER)}
    analyst_order["Risk Management"] = len(ANALYST_ORDER)  # Add Risk Management at the end

    return sorted(signals, key=lambda x: analyst_order.get(x[0], 999))


def print_trading_output(result: dict) -> None:
    """
    Print formatted trading results with colored tables for multiple tickers.

    Args:
        result (dict): Dictionary containing decisions and analyst signals for multiple tickers
    """
    decisions = result.get("decisions")
    if not decisions:
        print(f"{Fore.RED}No trading decisions available{Style.RESET_ALL}")
        return

    # Print decisions for each ticker
    for ticker, decision in decisions.items():
        print(f"\n{Fore.WHITE}{Style.BRIGHT}Analysis for {Fore.CYAN}{ticker}{Style.RESET_ALL}")
        print(f"{Fore.WHITE}{Style.BRIGHT}{'=' * 50}{Style.RESET_ALL}")

        # Prepare analyst signals table for this ticker
        table_data = []
        for agent, signals in result.get("analyst_signals", {}).items():
            if ticker not in signals:
                continue
                
            # Skip Risk Management agent in the signals section
            if agent == "risk_management_agent":
                continue

            signal = signals[ticker]
            agent_name = agent.replace("_agent", "").replace("_", " ").title()
            signal_type = signal.get("signal", "").upper()
            confidence = signal.get("confidence", 0)

            signal_color = {
                "BULLISH": Fore.GREEN,
                "BEARISH": Fore.RED,
                "NEUTRAL": Fore.YELLOW,
            }.get(signal_type, Fore.WHITE)
            
            # Get reasoning if available
            reasoning_str = ""
            if "reasoning" in signal and signal["reasoning"]:
                reasoning = signal["reasoning"]
                
                # Handle different types of reasoning (string, dict, etc.)
                if isinstance(reasoning, str):
                    reasoning_str = reasoning
                elif isinstance(reasoning, dict):
                    # Convert dict to string representation
                    reasoning_str = json.dumps(reasoning, indent=2)
                else:
                    # Convert any other type to string
                    reasoning_str = str(reasoning)
                
                # Wrap long reasoning text to make it more readable
                wrapped_reasoning = ""
                current_line = ""
                # Use a fixed width of 60 characters to match the table column width
                max_line_length = 60
                for word in reasoning_str.split():
                    if len(current_line) + len(word) + 1 > max_line_length:
                        wrapped_reasoning += current_line + "\n"
                        current_line = word
                    else:
                        if current_line:
                            current_line += " " + word
                        else:
                            current_line = word
                if current_line:
                    wrapped_reasoning += current_line
                
                reasoning_str = wrapped_reasoning

            table_data.append(
                [
                    f"{Fore.CYAN}{agent_name}{Style.RESET_ALL}",
                    f"{signal_color}{signal_type}{Style.RESET_ALL}",
                    f"{Fore.WHITE}{confidence}%{Style.RESET_ALL}",
                    f"{Fore.WHITE}{reasoning_str}{Style.RESET_ALL}",
                ]
            )

        # Sort the signals according to the predefined order
        table_data = sort_agent_signals(table_data)

        print(f"\n{Fore.WHITE}{Style.BRIGHT}AGENT ANALYSIS:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
        print(
            tabulate(
                table_data,
                headers=[f"{Fore.WHITE}Agent", "Signal", "Confidence", "Reasoning"],
                tablefmt="grid",
                colalign=("left", "center", "right", "left"),
            )
        )

        # Print Trading Decision Table
        action = decision.get("action", "").upper()
        action_color = {
            "BUY": Fore.GREEN,
            "SELL": Fore.RED,
            "HOLD": Fore.YELLOW,
            "COVER": Fore.GREEN,
            "SHORT": Fore.RED,
        }.get(action, Fore.WHITE)

        # Get reasoning and format it
        reasoning = decision.get("reasoning", "")
        # Wrap long reasoning text to make it more readable
        wrapped_reasoning = ""
        if reasoning:
            current_line = ""
            # Use a fixed width of 60 characters to match the table column width
            max_line_length = 60
            for word in reasoning.split():
                if len(current_line) + len(word) + 1 > max_line_length:
                    wrapped_reasoning += current_line + "\n"
                    current_line = word
                else:
                    if current_line:
                        current_line += " " + word
                    else:
                        current_line = word
            if current_line:
                wrapped_reasoning += current_line

        decision_data = [
            ["Action", f"{action_color}{action}{Style.RESET_ALL}"],
            ["Quantity", f"{action_color}{decision.get('quantity')}{Style.RESET_ALL}"],
            [
                "Confidence",
                f"{Fore.WHITE}{decision.get('confidence'):.1f}%{Style.RESET_ALL}",
            ],
            ["Reasoning", f"{Fore.WHITE}{wrapped_reasoning}{Style.RESET_ALL}"],
        ]
        
        print(f"\n{Fore.WHITE}{Style.BRIGHT}TRADING DECISION:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
        print(tabulate(decision_data, tablefmt="grid", colalign=("left", "left")))

    # Print Portfolio Summary
    print(f"\n{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY:{Style.RESET_ALL}")
    portfolio_data = []
    
    # Extract portfolio manager reasoning (common for all tickers)
    portfolio_manager_reasoning = None
    for ticker, decision in decisions.items():
        if decision.get("reasoning"):
            portfolio_manager_reasoning = decision.get("reasoning")
            break
            
    for ticker, decision in decisions.items():
        action = decision.get("action", "").upper()
        action_color = {
            "BUY": Fore.GREEN,
            "SELL": Fore.RED,
            "HOLD": Fore.YELLOW,
            "COVER": Fore.GREEN,
            "SHORT": Fore.RED,
        }.get(action, Fore.WHITE)
        portfolio_data.append(
            [
                f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
                f"{action_color}{action}{Style.RESET_ALL}",
                f"{action_color}{decision.get('quantity')}{Style.RESET_ALL}",
                f"{Fore.WHITE}{decision.get('confidence'):.1f}%{Style.RESET_ALL}",
            ]
        )

    headers = [f"{Fore.WHITE}Ticker", "Action", "Quantity", "Confidence"]
    
    # Print the portfolio summary table
    print(
        tabulate(
            portfolio_data,
            headers=headers,
            tablefmt="grid",
            colalign=("left", "center", "right", "right"),
        )
    )
    
    # Print Portfolio Manager's reasoning if available
    if portfolio_manager_reasoning:
        # Handle different types of reasoning (string, dict, etc.)
        reasoning_str = ""
        if isinstance(portfolio_manager_reasoning, str):
            reasoning_str = portfolio_manager_reasoning
        elif isinstance(portfolio_manager_reasoning, dict):
            # Convert dict to string representation
            reasoning_str = json.dumps(portfolio_manager_reasoning, indent=2)
        else:
            # Convert any other type to string
            reasoning_str = str(portfolio_manager_reasoning)
            
        # Wrap long reasoning text to make it more readable
        wrapped_reasoning = ""
        current_line = ""
        # Use a fixed width of 60 characters to match the table column width
        max_line_length = 60
        for word in reasoning_str.split():
            if len(current_line) + len(word) + 1 > max_line_length:
                wrapped_reasoning += current_line + "\n"
                current_line = word
            else:
                if current_line:
                    current_line += " " + word
                else:
                    current_line = word
        if current_line:
            wrapped_reasoning += current_line
            
        print(f"\n{Fore.WHITE}{Style.BRIGHT}Portfolio Strategy:{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{wrapped_reasoning}{Style.RESET_ALL}")


def print_backtest_results(table_rows: list) -> None:
    """Print the backtest results in a nicely formatted table"""
    # Clear the screen
    os.system("cls" if os.name == "nt" else "clear")

    # Split rows into ticker rows and summary rows
    ticker_rows = []
    summary_rows = []

    for row in table_rows:
        if isinstance(row[1], str) and "PORTFOLIO SUMMARY" in row[1]:
            summary_rows.append(row)
        else:
            ticker_rows.append(row)

    
    # Display latest portfolio summary
    if summary_rows:
        latest_summary = summary_rows[-1]
        print(f"\n{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY:{Style.RESET_ALL}")

        # Extract values and remove commas before converting to float
        cash_str = latest_summary[7].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")
        position_str = latest_summary[6].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")
        total_str = latest_summary[8].split("$")[1].split(Style.RESET_ALL)[0].replace(",", "")

        print(f"Cash Balance: {Fore.CYAN}${float(cash_str):,.2f}{Style.RESET_ALL}")
        print(f"Total Position Value: {Fore.YELLOW}${float(position_str):,.2f}{Style.RESET_ALL}")
        print(f"Total Value: {Fore.WHITE}${float(total_str):,.2f}{Style.RESET_ALL}")
        print(f"Return: {latest_summary[9]}")
        
        # Display performance metrics if available
        if latest_summary[10]:  # Sharpe ratio
            print(f"Sharpe Ratio: {latest_summary[10]}")
        if latest_summary[11]:  # Sortino ratio
            print(f"Sortino Ratio: {latest_summary[11]}")
        if latest_summary[12]:  # Max drawdown
            print(f"Max Drawdown: {latest_summary[12]}")

    # Add vertical spacing
    print("\n" * 2)

    # Print the table with just ticker rows
    print(
        tabulate(
            ticker_rows,
            headers=[
                "Date",
                "Ticker",
                "Action",
                "Quantity",
                "Price",
                "Shares",
                "Position Value",
                "Bullish",
                "Bearish",
                "Neutral",
            ],
            tablefmt="grid",
            colalign=(
                "left",  # Date
                "left",  # Ticker
                "center",  # Action
                "right",  # Quantity
                "right",  # Price
                "right",  # Shares
                "right",  # Position Value
                "right",  # Bullish
                "right",  # Bearish
                "right",  # Neutral
            ),
        )
    )

    # Add vertical spacing
    print("\n" * 4)


def format_backtest_row(
    date: str,
    ticker: str,
    action: str,
    quantity: float,
    price: float,
    shares_owned: float,
    position_value: float,
    bullish_count: int,
    bearish_count: int,
    neutral_count: int,
    is_summary: bool = False,
    total_value: float = None,
    return_pct: float = None,
    cash_balance: float = None,
    total_position_value: float = None,
    sharpe_ratio: float = None,
    sortino_ratio: float = None,
    max_drawdown: float = None,
) -> list[any]:
    """Format a row for the backtest results table"""
    # Color the action
    action_color = {
        "BUY": Fore.GREEN,
        "COVER": Fore.GREEN,
        "SELL": Fore.RED,
        "SHORT": Fore.RED,
        "HOLD": Fore.WHITE,
    }.get(action.upper(), Fore.WHITE)

    if is_summary:
        return_color = Fore.GREEN if return_pct >= 0 else Fore.RED
        return [
            date,
            f"{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY{Style.RESET_ALL}",
            "",  # Action
            "",  # Quantity
            "",  # Price
            "",  # Shares
            f"{Fore.YELLOW}${total_position_value:,.2f}{Style.RESET_ALL}",  # Total Position Value
            f"{Fore.CYAN}${cash_balance:,.2f}{Style.RESET_ALL}",  # Cash Balance
            f"{Fore.WHITE}${total_value:,.2f}{Style.RESET_ALL}",  # Total Value
            f"{return_color}{return_pct:+.2f}%{Style.RESET_ALL}",  # Return
            f"{Fore.YELLOW}{sharpe_ratio:.2f}{Style.RESET_ALL}" if sharpe_ratio is not None else "",  # Sharpe Ratio
            f"{Fore.YELLOW}{sortino_ratio:.2f}{Style.RESET_ALL}" if sortino_ratio is not None else "",  # Sortino Ratio
            f"{Fore.RED}{abs(max_drawdown):.2f}%{Style.RESET_ALL}" if max_drawdown is not None else "",  # Max Drawdown
        ]
    else:
        return [
            date,
            f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
            f"{action_color}{action.upper()}{Style.RESET_ALL}",
            f"{action_color}{quantity:,.0f}{Style.RESET_ALL}",
            f"{Fore.WHITE}{price:,.2f}{Style.RESET_ALL}",
            f"{Fore.WHITE}{shares_owned:,.0f}{Style.RESET_ALL}",
            f"{Fore.YELLOW}{position_value:,.2f}{Style.RESET_ALL}",
            f"{Fore.GREEN}{bullish_count}{Style.RESET_ALL}",
            f"{Fore.RED}{bearish_count}{Style.RESET_ALL}",
            f"{Fore.BLUE}{neutral_count}{Style.RESET_ALL}",
        ]


# --- PDF Generation Function ---

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'AI Hedge Fund Analysis Report', 0, 1, 'C')
        self.set_font('Arial', '', 8)
        self.cell(0, 5, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(2)

    def section_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 8, title, 0, 1, 'L')
        self.ln(1)

    def write_table(self, headers, data, col_widths):
        self.set_font('Arial', 'B', 9)
        # Header
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 7, header, 1, 0, 'C')
        self.ln()
        # Data
        self.set_font('Arial', '', 8)
        for row in data:
            for i, item in enumerate(row):
                # Use multi_cell for potentially long text like reasoning
                if i == len(row) - 1 and len(item) > (col_widths[i] / 2): # Heuristic for reasoning column
                     x = self.get_x()
                     y = self.get_y()
                     self.multi_cell(col_widths[i], 5, str(item), border=1, align='L')
                     self.set_xy(x + col_widths[i], y) # Move position for next cell
                else:
                    self.cell(col_widths[i], 5, str(item), 1, 0, 'L' if isinstance(item, str) else 'R')
            self.ln()
        self.ln(5) # Add space after table

    def write_key_value(self, key, value):
         self.set_font('Arial', 'B', 9)
         self.cell(40, 5, key, border='B')
         self.set_font('Arial', '', 9)
         # Use multi_cell for potentially long values like reasoning
         if isinstance(value, str) and len(value) > 80: # Heuristic for long text
             x = self.get_x()
             y = self.get_y()
             self.multi_cell(0, 5, value, border='B', align='L')
             self.set_xy(x, self.get_y()) # Reset X for next line, Y is handled by multi_cell
         else:
             self.cell(0, 5, str(value), border='B', ln=1)


def save_analysis_to_pdf(result: dict, filename: str = "ai_hedge_fund_report.pdf") -> None:
    """
    Saves the trading analysis results to a PDF file.

    Args:
        result (dict): Dictionary containing decisions and analyst signals.
        filename (str): The name of the output PDF file.
    """
    decisions = result.get("decisions")
    analyst_signals_data = result.get("analyst_signals", {})
    if not decisions:
        print(f"{Fore.RED}No trading decisions available to save to PDF.{Style.RESET_ALL}")
        return

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- Analysis per Ticker ---
    pdf.chapter_title("Ticker Analysis")

    for ticker, decision in decisions.items():
        pdf.section_title(f"Analysis for {ticker}")

        # Agent Analysis Table
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 6, "Agent Analysis:", 0, 1)
        agent_headers = ["Agent", "Signal", "Confidence", "Reasoning"]
        # Estimate column widths (total width ~190 for A4 portrait)
        agent_col_widths = [40, 20, 25, 105]
        agent_table_data = []

        # Sort agents for consistent order in PDF
        sorted_agent_keys = sorted(
            analyst_signals_data.keys(),
            key=lambda k: {name: idx for idx, (_, name) in enumerate(ANALYST_ORDER)}.get(k.replace('_agent', ''), 999)
        )

        for agent_key in sorted_agent_keys:
            signals = analyst_signals_data.get(agent_key, {})
            if ticker not in signals:
                continue
            if agent_key == "risk_management_agent": # Skip risk agent here
                 continue

            signal_data = signals[ticker]
            agent_name = agent_key.replace("_agent", "").replace("_", " ").title()
            signal_type = signal_data.get("signal", "").upper()
            confidence = f"{signal_data.get('confidence', 0):.1f}%"
            reasoning = signal_data.get("reasoning", "")
            # Basic text wrapping for PDF cell
            wrapped_reasoning = '\n'.join(textwrap.wrap(str(reasoning), width=60)) # Adjust width as needed

            agent_table_data.append([agent_name, signal_type, confidence, wrapped_reasoning])

        if agent_table_data:
            pdf.write_table(agent_headers, agent_table_data, agent_col_widths)
        else:
             pdf.set_font('Arial', '', 9)
             pdf.cell(0, 5, "No analyst signals available for this ticker.", 0, 1)
             pdf.ln(3)


        # Trading Decision
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 6, "Trading Decision:", 0, 1)
        pdf.write_key_value("Action", decision.get("action", "N/A").upper())
        pdf.write_key_value("Quantity", str(decision.get("quantity", "N/A")))
        pdf.write_key_value("Confidence", f"{decision.get('confidence', 0):.1f}%")
        pdf.write_key_value("Reasoning", str(decision.get("reasoning", "N/A")))
        pdf.ln(5)

    # --- Portfolio Summary ---
    pdf.add_page()
    pdf.chapter_title("Portfolio Summary")

    # Portfolio Decisions Table
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 6, "Decisions Summary:", 0, 1)
    summary_headers = ["Ticker", "Action", "Quantity", "Confidence"]
    summary_col_widths = [40, 40, 40, 40]
    summary_table_data = []
    portfolio_manager_reasoning = None

    for ticker, decision in decisions.items():
        # Capture portfolio manager reasoning (assuming it's the same in all decisions)
        if not portfolio_manager_reasoning and decision.get("reasoning"):
             portfolio_manager_reasoning = str(decision.get("reasoning", "N/A"))

        summary_table_data.append([
            ticker,
            decision.get("action", "N/A").upper(),
            str(decision.get("quantity", "N/A")),
            f"{decision.get('confidence', 0):.1f}%"
        ])

    pdf.write_table(summary_headers, summary_table_data, summary_col_widths)

    # Portfolio Strategy Reasoning
    if portfolio_manager_reasoning:
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 6, "Portfolio Strategy:", 0, 1)
        pdf.set_font('Arial', '', 9)
        pdf.multi_cell(0, 5, portfolio_manager_reasoning)
        pdf.ln(5)

    # --- Save PDF ---
    try:
        pdf.output(filename, "F")
        print(f"\n{Fore.GREEN}Successfully saved analysis report to: {filename}{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}Error saving PDF report to {filename}: {e}{Style.RESET_ALL}")

# --- End PDF Generation Function ---
