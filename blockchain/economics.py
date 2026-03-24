"""
Wrath of Cali Blockchain - Economic Thermodynamics Model
Based on elara2.txt specifications from Desktop

Features:
- Token emission curve
- Inflation control system
- Resource sinks
- Diminishing staking returns
- Quadratic governance weighting
- Anti-whale equilibrium mechanisms
- Era-based economic resets
"""
import math
from typing import Dict, Optional
from dataclasses import dataclass


# ============== CONSTANTS ==============
TOTAL_SUPPLY = 100_000_000  # 100M Calicos (from SPEC.md)

# Era configuration (each era is ~1 year in blocks)
BLOCKS_PER_ERA = 525_600  # ~1 year at 1 block/second

# Emission parameters
INITIAL_EMISSION_PER_BLOCK = 100  # Starting emission
EMISSION_DECAY_RATE = 0.95  # 5% reduction per era
MIN_EMISSION_PER_BLOCK = 1  # Minimum emission floor

# Staking parameters
BASE_STAKING_REWARD = 0.10  # 10% base APY
MIN_STAKING_REWARD = 0.02   # 2% minimum APY (diminishing returns)
STAKING_DIMINISH_FACTOR = 0.001  # Each 1000 calicos staked reduces rate slightly

# Governance parameters
QUADRATIC_COEFFICIENT = 0.01  # For quadratic voting weight

# Anti-whale parameters
LARGE_HOLDER_THRESHOLD = 1_000_000  # 1% of supply
WHALE_TAX_RATE = 0.02  # 2% extra tax on large holders
MAX_SINGLE_HOLDING = 10_000_000  # Max 10% of supply in one wallet

# Resource sink parameters
TRANSACTION_FEE_BURN = 0.5  # 50% of fees burned
GAME_PURCHASE_BURN = 0.10  # 10% of game purchases burned
SINK_TARGET_PERCENT = 0.30  # Target 30% of tokens in sinks annually


@dataclass
class EconomicState:
    """Current economic state"""
    current_era: int = 0
    total_burned: float = 0.0
    governance_treasury: float = 0.0
    resource_sinks: Dict[str, float] = None
    
    def __post_init__(self):
        if self.resource_sinks is None:
            self.resource_sinks = {
                "transaction_fees": 0.0,
                "game_purchases": 0.0,
                "governance_penalties": 0.0,
                "era_burns": 0.0
            }


class EmissionSchedule:
    """Token emission curve with era-based decay"""
    
    def __init__(self, current_era: int = 0):
        self.current_era = current_era
    
    def get_emission_per_block(self) -> float:
        """Calculate emission for current era with decay"""
        emission = INITIAL_EMISSION_PER_BLOCK * (EMISSION_DECAY_RATE ** self.current_era)
        return max(emission, MIN_EMISSION_PER_BLOCK)
    
    def get_annual_inflation_rate(self, total_staked: float, total_circulating: float) -> float:
        """Calculate effective inflation rate"""
        if total_circulating <= 0:
            return 0.0
        annual_emission = self.get_emission_per_block() * BLOCKS_PER_ERA
        return (annual_emission / total_circulating) * 100
    
    def advance_era(self):
        """Move to next era"""
        self.current_era += 1
    
    def get_era_info(self) -> Dict:
        """Get info about current era"""
        return {
            "era": self.current_era,
            "emission_per_block": self.get_emission_per_block(),
            "annual_emission": self.get_emission_per_block() * BLOCKS_PER_ERA,
            "decay_factor": EMISSION_DECAY_RATE ** self.current_era
        }


class StakingRewards:
    """Diminishing staking returns based on amount staked"""
    
    @staticmethod
    def calculate_apr(staked_amount: float) -> float:
        """
        Calculate APR with diminishing returns.
        Larger stakers get lower yields to encourage decentralization.
        """
        # Base reward
        apr = BASE_STAKING_REWARD
        
        # Apply diminishing factor based on stake size
        # For every 1000 Calicos staked, reduce rate slightly
        diminish = staked_amount * STAKING_DIMINISH_FACTOR
        apr = max(apr - diminish, MIN_STAKING_REWARD)
        
        return apr
    
    @staticmethod
    def calculate_reward(staked_amount: float, blocks: int = 1) -> float:
        """Calculate actual reward for staking over blocks"""
        apr = StakingRewards.calculate_apr(staked_amount)
        # APR to per-block rate
        per_block_rate = apr / BLOCKS_PER_ERA
        return staked_amount * per_block_rate * blocks
    
    @staticmethod
    def get_lock_period_multiplier(days_staked: int) -> float:
        """
        Bonus for longer lock periods.
        0-7 days: 1.0x
        7-30 days: 1.25x
        30-90 days: 1.5x
        90+ days: 2.0x
        """
        if days_staked >= 90:
            return 2.0
        elif days_staked >= 30:
            return 1.5
        elif days_staked >= 7:
            return 1.25
        return 1.0


class GovernanceWeighting:
    """Quadratic governance weighting"""
    
    @staticmethod
    def calculate_vote_weight(staked_amount: float) -> float:
        """
        Quadratic voting - reduces whale advantage.
        Weight = sqrt(staked_amount) * coefficient
        """
        if staked_amount <= 0:
            return 0.0
        return math.sqrt(staked_amount) * QUADRATIC_COEFFICIENT
    
    @staticmethod
    def calculate_proposal_quorum(total_staked: float) -> int:
        """Minimum votes needed for proposal to pass"""
        return int(total_staked * 0.10)  # 10% of staked tokens


class AntiWhaleMechanisms:
    """Anti-whale equilibrium mechanisms"""
    
    @staticmethod
    def calculate_whale_tax(balance: float) -> float:
        """Calculate additional tax for large holders"""
        if balance > LARGE_HOLDER_THRESHOLD:
            excess = balance - LARGE_HOLDER_THRESHOLD
            return excess * WHALE_TAX_RATE
        return 0.0
    
    @staticmethod
    def check_holding_limit(balance: float) -> tuple[bool, str]:
        """Check if holding exceeds maximum allowed"""
        if balance > MAX_SINGLE_HOLDING:
            return False, f"Exceeded max holding of {MAX_SINGLE_HOLDING} Calicos"
        return True, "OK"
    
    @staticmethod
    def get_transfer_tax(sender_balance: float, amount: float) -> float:
        """
        Progressive tax on large transfers.
        Encourages smaller, more frequent transactions.
        """
        if sender_balance > LARGE_HOLDER_THRESHOLD:
            # 1% tax on transfers over 10,000 for large holders
            if amount > 10_000:
                return amount * 0.01
        return 0.0


class ResourceSinks:
    """Resource sinks to remove tokens from circulation"""
    
    def __init__(self, state: EconomicState):
        self.state = state
    
    def burn_transaction_fee(self, fee: float) -> float:
        """Burn 50% of transaction fees"""
        burn_amount = fee * TRANSACTION_FEE_BURN
        self.state.total_burned += burn_amount
        self.state.resource_sinks["transaction_fees"] += burn_amount
        return burn_amount
    
    def burn_game_purchase(self, amount: float) -> float:
        """Burn 10% of game purchases"""
        burn_amount = amount * GAME_PURCHASE_BURN
        self.state.total_burned += burn_amount
        self.state.resource_sinks["game_purchases"] += burn_amount
        return burn_amount
    
    def burn_penalty(self, amount: float) -> float:
        """Burn governance penalties"""
        self.state.total_burned += amount
        self.state.resource_sinks["governance_penalties"] += amount
        return amount
    
    def era_burn(self) -> float:
        """
        Era-based economic reset - burn excess tokens.
        Called at the start of each new era.
        """
        # Calculate burn to maintain ~30% in sinks
        # This is a simplified model - can be adjusted
        era_burn = self.state.total_burned * 0.01  # 1% of total burned
        self.state.resource_sinks["era_burns"] += era_burn
        return era_burn
    
    def get_sink_stats(self) -> Dict:
        """Get current sink statistics"""
        total_sinks = sum(self.state.resource_sinks.values())
        return {
            "total_burned": self.state.total_burned,
            "burn_percentage": (self.state.total_burned / TOTAL_SUPPLY) * 100,
            "sinks": self.state.resource_sinks,
            "treasury": self.state.governance_treasury
        }


class EconomicController:
    """Main controller for all economic systems"""
    
    def __init__(self):
        self.state = EconomicState()
        self.emission = EmissionSchedule()
        self.sinks = ResourceSinks(self.state)
    
    def process_block(self, validator_reward: float = None) -> Dict:
        """Process economic updates for a new block"""
        # Get emission for this block
        emission = self.emission.get_emission_per_block()
        
        # Calculate inflation
        total_circulating = TOTAL_SUPPLY - self.state.total_burned
        inflation_rate = self.emission.get_annual_inflation_rate(
            0,  # TODO: pass actual staked amount
            total_circulating
        )
        
        return {
            "emission": emission,
            "inflation_rate": inflation_rate,
            "total_burned": self.state.total_burned,
            "circulating": total_circulating,
            "era": self.emission.current_era
        }
    
    def process_era_change(self) -> Dict:
        """Handle transition to new era"""
        # Advance emission schedule
        self.emission.advance_era()
        
        # Trigger era burn
        era_burn = self.sinks.era_burn()
        
        # Get new era info
        era_info = self.emission.get_era_info()
        
        return {
            "new_era": self.emission.current_era,
            "era_burn": era_burn,
            "new_emission": era_info["emission_per_block"],
            "total_burned": self.state.total_burned
        }
    
    def get_full_economic_snapshot(self) -> Dict:
        """Get complete economic state"""
        total_circulating = TOTAL_SUPPLY - self.state.total_burned
        
        return {
            "supply": {
                "total": TOTAL_SUPPLY,
                "circulating": total_circulating,
                "burned": self.state.total_burned,
                "burn_percentage": (self.state.total_burned / TOTAL_SUPPLY) * 100
            },
            "emission": self.emission.get_era_info(),
            "inflation": {
                "current_rate": self.emission.get_annual_inflation_rate(0, total_circulating),
                "target": SINK_TARGET_PERCENT * 100
            },
            "sinks": self.sinks.get_sink_stats(),
            "era": self.emission.current_era
        }


# ============== CLI / TEST ==============
if __name__ == "__main__":
    # Test the economic model
    controller = EconomicController()
    
    print("=== Wrath of Cali Economic Thermodynamics ===\n")
    
    # Show initial state
    snapshot = controller.get_full_economic_snapshot()
    print("Initial Economic State:")
    print(f"  Total Supply: {snapshot['supply']['total']:,.0f} Calicos")
    print(f"  Current Era: {snapshot['era']}")
    print(f"  Emission/Block: {snapshot['emission']['emission_per_block']:.2f}")
    print(f"  Annual Inflation: {snapshot['inflation']['current_rate']:.2f}%")
    print()
    
    # Test staking rewards
    print("Staking Rewards (APR):")
    for stake in [1000, 10000, 100000, 1000000]:
        apr = StakingRewards.calculate_apr(stake)
        print(f"  {stake:>10,} Calicos: {apr*100:.2f}%")
    print()
    
    # Test governance weighting
    print("Governance Vote Weight (Quadratic):")
    for stake in [1000, 10000, 100000, 1000000]:
        weight = GovernanceWeighting.calculate_vote_weight(stake)
        print(f"  {stake:>10,} Calicos: {weight:.4f}")
    print()
    
    # Test anti-whale
    print("Anti-Whale Tax:")
    for balance in [500000, 1000000, 5000000, 10000000]:
        tax = AntiWhaleMechanisms.calculate_whale_tax(balance)
        print(f"  {balance:>10,} balance: {tax:,.0f} tax")
    print()
    
    # Simulate era change
    print("Simulating Era Change...")
    result = controller.process_era_change()
    print(f"  New Era: {result['new_era']}")
    print(f"  New Emission: {result['new_emission']:.2f}")
    print(f"  Era Burn: {result['era_burn']:.2f}")