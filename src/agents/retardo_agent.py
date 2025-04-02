from graph.state import AgentState, show_agent_reasoning
from tools.api import (
    get_financial_metrics,
    get_market_cap,
    search_line_items,
    get_insider_trades,
    get_company_news,
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage # Added SystemMessage
from pydantic import BaseModel
import json
from typing_extensions import Literal
from utils.progress import progress
from utils.llm import call_llm
import os

class PersonalityTraderSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str

class PersonalityTrader:
    def __init__(self, config_path='agent_config.json'):
        # Load configuration from file; if not found, use defaults.
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                "personality": "INTJ",
                "enneagram": "5",
                "base_threshold": 0.05,
                "risk_appetite": 1.0,
                "personality_adjustments": {
                    "INTJ": 0.85,
                    "ENTJ": 0.80,
                    "INFJ": 1.10,
                    "ENFJ": 1.00,
                    "ISTJ": 1.15,
                    "ESTJ": 1.05,
                    "ISFJ": 1.20,
                    "ESFJ": 1.10,
                    "ISTP": 0.95,
                    "ESTP": 0.75,
                    "INFP": 1.15,
                    "ENFP": 0.90,
                    "INTP": 0.95,
                    "ENTP": 0.80
                },
                "enneagram_adjustments": {
                    "1": 1.10,
                    "2": 1.00,
                    "3": 0.90,
                    "4": 1.00,
                    "5": 0.85,
                    "6": 1.15,
                    "7": 0.75,
                    "8": 0.85,
                    "9": 1.10
                }
            }
        
        self.personality = self.config.get("personality", "INTJ")
        self.enneagram = self.config.get("enneagram", "5")
        self.base_threshold = self.config.get("base_threshold", 0.05)
        self.risk_appetite = self.config.get("risk_appetite", 1.0)
        
        # --- Detailed MBTI personality descriptions ---
        self.personality_traits = {
            "INTJ": (
                "The Architect: Highly analytical, strategic, and visionary. Excels in long-term planning and problem solving, "
                "but can be overcritical and dismissive of emotional input."
            ),
            "ENTJ": (
                "The Commander: Bold, assertive, and decisive. A natural leader who drives projects forward, though sometimes "
                "aggressive and overly dominant."
            ),
            "INFJ": (
                "The Advocate: Insightful, empathetic, and principled. Driven by strong values, but can be overly idealistic "
                "and struggle with practical implementation."
            ),
            "ENFJ": (
                "The Protagonist: Charismatic, inspiring, and warm. Excellent at rallying people around a vision, yet may overcommit "
                "or be overly sensitive to criticism."
            ),
            "ISTJ": (
                "The Logistician: Dependable, methodical, and practical. Values order and tradition, though sometimes resists change "
                "and can be seen as rigid."
            ),
            "ESTJ": (
                "The Executive: Organized and decisive, with a focus on efficiency. Effective in managing tasks and people, yet can be "
                "inflexible or overly conservative."
            ),
            "ISFJ": (
                "The Defender: Warm, meticulous, and protective. Committed to maintaining stability, but may be overly risk-averse "
                "and slow to act on new opportunities."
            ),
            "ESFJ": (
                "The Consul: Sociable, nurturing, and conscientious. Prioritizes harmony and cooperation, though may lack innovation "
                "and be overly reliant on consensus."
            ),
            "ISTP": (
                "The Virtuoso: Practical, adaptable, and action-oriented. Excels at troubleshooting and hands-on problem solving, "
                "but sometimes makes impulsive decisions."
            ),
            "ESTP": (
                "The Entrepreneur: Energetic, perceptive, and bold. Thrives in fast-paced environments, yet may focus too much on short-term gains "
                "and overlook long-term risks."
            ),
            "INFP": (
                "The Mediator: Idealistic, creative, and deeply empathetic. Guided by core values and intuition, though occasionally indecisive "
                "and overly sensitive."
            ),
            "ENFP": (
                "The Campaigner: Enthusiastic, imaginative, and spontaneous. Generates innovative ideas and adapts easily, but may struggle with follow-through "
                "and discipline."
            ),
            "INTP": (
                "The Logician: Analytical, inventive, and intellectually curious. Enjoys dissecting complex problems, yet can appear detached "
                "and overly skeptical."
            ),
            "ENTP": (
                "The Debater: Quick-witted, resourceful, and unafraid to challenge conventional wisdom. Sparks innovation through debate, but may be inconsistent "
                "or argumentative."
            )
        }
        
        # --- Detailed Enneagram descriptions ---
        self.enneagram_traits = {
            "1": (
                "The Reformer: Principled, purposeful, and self-disciplined. Strives for integrity and high standards, but may be overly critical "
                "and rigid."
            ),
            "2": (
                "The Helper: Warm, caring, and interpersonal. Generous with support and kindness, yet sometimes overextends and seeks external validation."
            ),
            "3": (
                "The Achiever: Ambitious, adaptive, and success-driven. Highly motivated and efficient, but may become overly competitive or image-conscious."
            ),
            "4": (
                "The Individualist: Expressive, creative, and introspective. Values authenticity and depth, yet can be moody and self-absorbed."
            ),
            "5": (
                "The Investigator: Innovative, perceptive, and curious. Seeks deep understanding and competence, but may withdraw and become detached."
            ),
            "6": (
                "The Loyalist: Committed, security-oriented, and reliable. Builds strong bonds and values preparedness, though can be anxious and indecisive."
            ),
            "7": (
                "The Enthusiast: Spontaneous, versatile, and optimistic. Loves adventure and new experiences, but may scatter focus and avoid discomfort."
            ),
            "8": (
                "The Challenger: Assertive, decisive, and protective. Commands respect and leads confidently, yet may be confrontational and overly controlling."
            ),
            "9": (
                "The Peacemaker: Receptive, reassuring, and agreeable. Seeks harmony and balance, but may become complacent and avoid necessary conflict."
            )
        }
        
        self.personality_adjustments = self.config.get("personality_adjustments", {})
        self.enneagram_adjustments = self.config.get("enneagram_adjustments", {})
        self.personality_adjustment = self.personality_adjustments.get(self.personality, 1.0)
        self.enneagram_adjustment = self.enneagram_adjustments.get(self.enneagram, 1.0)

    def generate_prompt(self) -> str:
        """Generates the static instruction part of the system prompt."""
        personality_desc = self.personality_traits.get(self.personality, "")
        enneagram_desc = self.enneagram_traits.get(self.enneagram, "")

        instructions = (
            f"You are a Personality Trader AI agent whose decisions are deeply influenced by your unique character.\n"
            f"Your MBTI personality type is {self.personality}: {personality_desc}\n"
            f"Your Enneagram type is {self.enneagram}: {enneagram_desc}\n\n"
            "When analyzing market data, integrate your strengths and be mindful of your potential pitfalls. "
            "For example, if you are highly analytical, rely on quantitative evidence; if you are more spontaneous, "
            "be alert to rapid market changes while tempering impulsiveness with caution.\n\n"
            "Your task is to evaluate the market data provided (implicitly) and generate a trading signal. "
            "Your response should include:\n"
            "1. A clear decision: bullish, bearish, or neutral.\n"
            "2. A confidence level (0-100) reflecting your personality-driven risk appetite.\n"
            "3. Detailed reasoning that incorporates at least 2-3 aspects of your personality and enneagram traits, "
            "including any typical drawbacks you normally mitigate.\n"
            "4. Relevant quantitative evidence (e.g., price deviations, trend analysis).\n\n"
            "Return your response strictly as a JSON object with the following keys: 'signal' (string: 'bullish', 'bearish', or 'neutral'), 'confidence' (float: 0-100), and 'reasoning' (string)." # Describe format, don't show example
        )
        return instructions

    def decide(self, market_data: dict) -> str:
        # Calculate an adjusted threshold based on personality and enneagram multipliers.
        adjusted_threshold = self.base_threshold * self.personality_adjustment * self.enneagram_adjustment
        print(f"Personality: {self.personality} (multiplier: {self.personality_adjustment})")
        print(f"Enneagram: {self.enneagram} (multiplier: {self.enneagram_adjustment})")
        print(f"Adjusted threshold: {adjusted_threshold:.2%}")
        
        current_price = market_data.get("price")
        fair_value = market_data.get("fair_value")
        
        if current_price < fair_value * (1 - adjusted_threshold):
            return "bullish"
        elif current_price > fair_value * (1 + adjusted_threshold):
            return "bearish"
        else:
            return "neutral"

def generate_personality_trader_output( # Removed analysis_data, personality, enneagram parameters
    ticker: str,
    # analysis_data: dict, # Removed
    model_name: str,
    model_provider: str,
    # personality: str, # Removed
    # enneagram: str,   # Removed
) -> PersonalityTraderSignal:
    """
    Generates a trading signal based on the PersonalityTrader agent's analysis,
    using the configuration loaded from agent_config.json.
    """
    # Instantiate the agent - this will load agent_config.json by default
    # Ensure the config file is in the expected location relative to execution,
    # or pass an explicit path if needed.
    # Assuming execution from project root, the default 'agent_config.json'
    # might need to be 'src/agents/agent_config.json'. Let's adjust the default path.
    config_file_path = os.path.join('src', 'agents', 'agent_config.json')
    if not os.path.exists(config_file_path):
        # Fallback if not found in src/agents (e.g., running from src/agents dir)
        config_file_path = 'agent_config.json'

    agent = PersonalityTrader(config_path=config_file_path)

    # --- Construct simplified prompt string ---
    # The agent instance now holds the config loaded from the file
    system_instructions = agent.generate_prompt()

    # Simple human request focusing on the ticker and desired output format
    human_request_string = (
        f"\n\nAnalyze the stock with ticker {ticker} based on your personality profile and the instructions above. "
        "Generate the trading signal in the specified JSON format."
    )

    # Combine instructions and request
    final_prompt_string = f"{system_instructions}{human_request_string}"

    # Wrap the final string in a HumanMessage list
    prompt_messages = [HumanMessage(content=final_prompt_string)]
    # --- End prompt construction ---

    def create_default_personality_trader_signal():
        return PersonalityTraderSignal(
            signal="neutral",
            confidence=0.0,
            reasoning="Error in analysis, defaulting to neutral"
        )
    
    return call_llm(
        prompt=prompt_messages, # Pass the list with HumanMessage
        model_name=model_name,
        model_provider=model_provider,
        pydantic_model=PersonalityTraderSignal,
        agent_name="personality_trader_agent",
        default_factory=create_default_personality_trader_signal,
    )

def personality_trader_agent(state: AgentState):
    """
    Analyzes stocks using personality-based decision making.
    This agent tailors its investment decisions based on its MBTI and Enneagram traits.
    """
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]
    
    analysis_data_all = {}
    trader_analysis = {}
    
    for ticker in tickers:
        progress.update_status("personality_trader_agent", ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="annual", limit=10)
        
        progress.update_status("personality_trader_agent", ticker, "Gathering financial line items")
        financial_line_items = search_line_items(
            ticker,
            [
                "revenue",
                "net_income",
                "operating_income",
                "return_on_invested_capital",
                "gross_margin",
                "operating_margin",
                "free_cash_flow",
                "capital_expenditure",
                "cash_and_equivalents",
                "total_debt",
                "shareholders_equity",
                "outstanding_shares",
                "research_and_development",
                "goodwill_and_intangible_assets",
            ],
            end_date,
            period="annual",
            limit=10
        )
        
        progress.update_status("personality_trader_agent", ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date)
        
        progress.update_status("personality_trader_agent", ticker, "Fetching insider trades")
        insider_trades = get_insider_trades(
            ticker,
            end_date,
            start_date=None,
            limit=100
        )
        
        progress.update_status("personality_trader_agent", ticker, "Fetching company news")
        company_news = get_company_news(
            ticker,
            end_date,
            start_date=None,
            limit=100
        )
        
        # Compile a simple analysis data structure, converting Pydantic models to dicts.
        analysis_data = {
            "metrics": [metric.model_dump() for metric in metrics] if metrics else None,
            "financial_line_items": [item.model_dump() for item in financial_line_items] if financial_line_items else None,
            "market_cap": market_cap,
            "insider_trades": [trade.model_dump() for trade in insider_trades] if insider_trades else None,
            "company_news": [news.model_dump() for news in company_news] if company_news else None,
        }
        
        analysis_data_all[ticker] = analysis_data
        
        # Generate a personality-driven trading signal.
        # Remove personality/enneagram args as they are now loaded from config by the agent instance
        trader_signal = generate_personality_trader_output(
            ticker=ticker,
            model_name=state["metadata"]["model_name"],
            model_provider=state["metadata"]["model_provider"],
            # personality=state["metadata"].get("personality", "INTJ"), # Removed
            # enneagram=state["metadata"].get("enneagram", "5")        # Removed
        )

        trader_analysis[ticker] = {
            "signal": trader_signal.signal,
            "confidence": trader_signal.confidence,
            "reasoning": trader_signal.reasoning
        }
        
        progress.update_status("personality_trader_agent", ticker, "Done")
    
    message = HumanMessage(
        content=json.dumps(trader_analysis),
        name="personality_trader_agent"
    )
    
    if state["metadata"].get("show_reasoning"):
        show_agent_reasoning(trader_analysis, "Personality Trader Agent")
    
    state["data"]["analyst_signals"]["personality_trader_agent"] = trader_analysis
    
    return {
        "messages": [message],
        "data": state["data"]
    }
