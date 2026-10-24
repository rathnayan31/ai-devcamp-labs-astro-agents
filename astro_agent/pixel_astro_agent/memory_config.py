"""Memory Bank configuration restricted to response-style preferences."""

from vertexai._genai.types import ManagedTopicEnum
from vertexai._genai.types import (
    MemoryBankCustomizationConfig as CustomizationConfig,
)
from vertexai._genai.types import (
    MemoryBankCustomizationConfigMemoryTopic as MemoryTopic,
)
from vertexai._genai.types import (
    MemoryBankCustomizationConfigMemoryTopicManagedMemoryTopic as ManagedMemoryTopic,
)
from vertexai._genai.types import (
    ReasoningEngineContextSpecMemoryBankConfig as MemoryBankConfig,
)
from vertexai._genai.types import (
    ReasoningEngineContextSpecMemoryBankConfigTtlConfig as TtlConfig,
)

# Lab 2: preferences expire after 90 days unless the user restates them.
MEMORY_TTL = f"{90 * 24 * 60 * 60}s"

memory_bank_config = MemoryBankConfig(
    customization_configs=[
        CustomizationConfig(
            memory_topics=[
                MemoryTopic(
                    managed_memory_topic=ManagedMemoryTopic(
                        managed_topic_enum=ManagedTopicEnum.USER_PREFERENCES,
                    ),
                ),
            ],
        ),
    ],
    ttl_config=TtlConfig(default_ttl=MEMORY_TTL),
)
