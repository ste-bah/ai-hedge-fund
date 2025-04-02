import json
import os

# Assume ChatPromptTemplate is a helper from the project to build prompts.
from some_module import ChatPromptTemplate  # Replace with the actual import path

# Optional type alias for clarity.
class PersonalityTraderSignal(dict):
    pass

class PersonalityTrader:
    def __init__(self, config_path='agent_config.json'):
        # Load configuration from file; if not available, defaults will be used.
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        else:
            # Default config for testing purposes.
            self.config = {"personality": "INTJ", "enneagram": "5"}
        
        # Set personality and enneagram type.
        self.personality = self.config.get("personality", "INTJ")
        self.enneagram = self.config.get("enneagram", "5")
        
        # --- Define detailed personality trait narratives ---
        self.personality_traits = {
            "INTJ": (
                "The Architect: Highly analytical, strategic, and visionary. INTJs excel at long-term planning "
                "and are self-confident in their ability to solve complex problems. However, they can sometimes be "
                "overly critical, dismissive of emotional input, and may struggle with interpersonal nuances."
            ),
            "ENTJ": (
                "The Commander: Bold, assertive, and natural leaders who excel at organizing and driving projects forward. "
                "ENTJs are decisive and strategic, yet they may come off as overly aggressive or insensitive to others' emotions."
            ),
            "INFJ": (
                "The Advocate: Insightful, empathetic, and principled, INFJs possess a deep understanding of people and ideas. "
                "They are driven by their values but can become overly idealistic and may struggle with practical implementation."
            ),
            "ENFJ": (
                "The Protagonist: Charismatic, inspirational, and warm, ENFJs are adept at rallying others around a cause. "
                "Their empathetic nature drives them to help, yet they might overcommit or be overly sensitive to criticism."
            ),
            "ISTJ": (
                "The Logistician: Dependable, methodical, and practical, ISTJs value tradition, order, and reliability. "
                "Their structured approach ensures consistency, but they may resist change and be perceived as inflexible."
            ),
            "ESTJ": (
                "The Executive: Organized, pragmatic, and decisive, ESTJs are effective at managing projects and people. "
                "They prioritize efficiency and clear guidelines, though this can sometimes lead to rigidity and a lack of adaptability."
            ),
            "ISFJ": (
                "The Defender: Warm, supportive, and detail-oriented, ISFJs are highly dedicated and reliable. "
                "They care deeply about others and maintain stability, but their risk-averse nature may hinder bold decision-making."
            ),
            "ESFJ": (
                "The Consul: Outgoing, nurturing, and conscientious, ESFJs excel at fostering community and ensuring harmony. "
                "They are attuned to the needs of others, yet they can be overly reliant on external validation and resist innovation."
            ),
            "ISTP": (
                "The Virtuoso: Logical, resourceful, and action-oriented, ISTPs excel at troubleshooting and practical problem-solving. "
                "Their spontaneity drives swift decisions, though it may also lead to impulsiveness and a disregard for long-term planning."
            ),
            "ESTP": (
                "The Entrepreneur: Energetic, perceptive, and bold, ESTPs thrive in fast-paced environments. "
                "They are quick-thinking and daring, but their focus on immediate gains can sometimes result in overlooking long-term risks."
            ),
            "INFP": (
                "The Mediator: Idealistic, creative, and deeply empathetic, INFPs are driven by their core values and imagination. "
                "They bring a human touch to their analysis, yet their idealism may sometimes make practical decision-making challenging."
            ),
            "ENFP": (
                "The Campaigner: Enthusiastic, imaginative, and spontaneous, ENFPs excel at generating innovative ideas "
                "and connecting with others. They can be highly adaptable but may struggle with discipline and follow-through."
            ),
            "INTP": (
                "The Logician: Analytical, inventive, and intellectually curious, INTPs enjoy dissecting complex problems "
                "with logical precision. Their deep analysis can be invaluable, though they may appear detached or overly skeptical."
            ),
            "ENTP": (
                "The Debater: Quick-witted, resourceful, and intellectually agile, ENTPs relish challenging conventional wisdom. "
                "Their love for debate fuels innovation, but they might come off as argumentative or inconsistent in execution."
            )
        }
        
        # --- Define detailed enneagram trait narratives ---
        self.enneagram_traits = {
            "1": (
                "The Reformer: Principled, purposeful, and self-disciplined, Type 1s strive for integrity and high standards. "
                "They are ethical and meticulous but can be overly critical of themselves and others, sometimes becoming rigid."
            ),
            "2": (
                "The Helper: Warm, caring, and interpersonal, Type 2s are generous and empathetic. "
                "They excel at nurturing relationships but may overextend themselves or become overly dependent on others’ validation."
            ),
            "3": (
                "The Achiever: Success-driven, adaptable, and image-conscious, Type 3s are highly motivated to excel. "
                "They are efficient and goal-oriented, yet can sometimes become overly competitive or overly focused on appearances."
            ),
            "4": (
                "The Individualist: Expressive, creative, and deeply introspective, Type 4s value authenticity and emotional depth. "
                "They bring unique insights and creativity, but their sensitivity can lead to mood swings and self-absorption."
            ),
            "5": (
                "The Investigator: Innovative, perceptive, and curious, Type 5s seek understanding and competence. "
                "They are self-sufficient and analytical, yet may become overly detached or isolated when overwhelmed by their inner world."
            ),
            "6": (
                "The Loyalist: Committed, security-oriented, and reliable, Type 6s value loyalty and preparedness. "
                "They excel in building trust but can be prone to anxiety and indecision when faced with uncertainty."
            ),
            "7": (
                "The Enthusiast: Spontaneous, versatile, and optimistic, Type 7s love new experiences and adventure. "
                "They bring energy and enthusiasm but may avoid discomfort by staying overly busy or scattered in focus."
            ),
            "8": (
                "The Challenger: Assertive, decisive, and protective, Type 8s are natural leaders who value strength and autonomy. "
                "They are confident and direct, though they might struggle with vulnerability and can sometimes be confrontational."
            ),
            "9": (
                "The Peacemaker: Receptive, reassuring, and agreeable, Type 9s value harmony and balance. "
                "They excel at mediating conflicts but may become complacent or avoid necessary confrontations."
            )
        }
        
        # --- Define adjustment multipliers for decision thresholds ---
        # Lower multipliers result in a lower threshold (more likely to trade) while higher values indicate a more cautious stance.
        self.personality_adjustments = {
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
        }
        self.enneagram_adjustments = {
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
        
        self.personality_adjustment = self.personality_adjustments.get(self.personality, 1.0)
        self.enneagram_adjustment = self.enneagram_adjustments.get(self.enneagram, 1.0)
        
        # Base threshold for decision (e.g., a 5% deviation from fair value triggers a signal).
        self.base_threshold = 0.05

    def generate_prompt(self, ticker: str, analysis_data: dict) -> str:
        """
        Generate a system prompt that includes market data and detailed personality/enneagram narratives.
        """
        personality_description = self.personality_traits.get(self.personality, "")
        enneagram_description = self.enneagram_traits.get(self.enneagram, "")
        
        system_message = (
            f"You are a trading AI agent whose decisions are deeply influenced by your personality.\n"
            f"Your MBTI personality type is {self.personality}: {personality_description}\n"
            f"Your Enneagram type is {self.enneagram}: {enneagram_description}\n\n"
            "When analyzing the market data, you must incorporate both the strengths and weaknesses of your profile. "
            "For example, if your personality is highly analytical, lean heavily on quantitative data; if you are more "
            "spontaneous, be alert to rapid market changes but counterbalance with caution.\n\n"
            "Your task is to evaluate the following market data and generate a trading signal. Ensure you:\n"
            "1. Clearly state your decision (bullish, bearish, or neutral).\n"
            "2. Provide a confidence level (0-100) that reflects your personality-driven risk appetite.\n"
            "3. Detail your reasoning, incorporating at least 2-3 aspects of your personality and enneagram traits—"
            "including potential drawbacks you normally guard against.\n"
            "4. Cite relevant quantitative evidence (e.g., price deviations, trend percentages).\n\n"
            "Market data for analysis:\n"
            f"Ticker: {ticker}\n"
            f"{json.dumps(analysis_data, indent=2)}\n\n"
            "Return your response in the following JSON format:\n"
            "{\n"
            '  "signal": "bullish/bearish/neutral",\n'
            '  "confidence": float (0-100),\n'
            '  "reasoning": "string"\n'
            "}\n"
        )
        return system_message

    def decide(self, market_data: dict) -> str:
        """
        Decide on a trading signal based on market data and personality-driven adjustments.
        """
        # Compute the adjusted threshold from the base threshold and multipliers.
        adjusted_threshold = self.base_threshold * self.personality_adjustment * self.enneagram_adjustment

        # Debug/log output:
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

def generate_personality_trader_output(
    ticker: str,
    analysis_data: dict,
    model_name: str,
    model_provider: str,
    personality: str,
    enneagram: str,
) -> PersonalityTraderSignal:
    """
    Generates a trading signal based on the PersonalityTrader's decision process,
    incorporating the unique attributes of the specified MBTI personality and enneagram types.
    """
    # Override configuration with the provided personality and enneagram.
    config = {"personality": personality, "enneagram": enneagram}
    
    # Create an agent instance and override its configuration.
    agent = PersonalityTrader()
    agent.config = config
    agent.personality = personality
    agent.enneagram = enneagram
    agent.personality_adjustment = agent.personality_adjustments.get(personality, 1.0)
    agent.enneagram_adjustment = agent.enneagram_adjustments.get(enneagram, 1.0)
    
    # Generate the system prompt that frames the agent’s analysis with detailed personality traits.
    system_prompt = agent.generate_prompt(ticker, analysis_data)
    
    # Define the human instruction message.
    human_prompt = (
        "Based on the system prompt above, analyze the provided market data and generate a trading signal. "
        "Return your response in JSON format with the keys 'signal', 'confidence', and 'reasoning'."
    )
    
    # Construct the prompt template using both messages.
    template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt)
    ])
    
    prompt = template.invoke({
        "analysis_data": json.dumps(analysis_data, indent=2),
        "ticker": ticker
    })
    
    return prompt

# --- Example usage ---
if __name__ == "__main__":
    # Sample market data
    market_data_example = {
        "price": 95,
        "fair_value": 100
    }
    analysis_data_example = {
        "price_trend": "downward",
        "volume": 1000000,
        "key_metrics": {
            "ROIC": 15,
            "margin": 20
        }
    }
    
    output = generate_personality_trader_output(
        ticker="XYZ",
        analysis_data=analysis_data_example,
        model_name="gpt-4",
        model_provider="OpenAI",
        personality="INTJ",
        enneagram="5"
    )
    print(output)
