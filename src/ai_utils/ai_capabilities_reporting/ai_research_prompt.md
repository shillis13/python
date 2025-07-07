# AI Platform Capabilities Research Prompt

## Objective
Research and document the current capabilities of [AI_PLATFORM_NAME] from a user perspective, creating a comprehensive, living document that can be periodically updated and compared across AI platforms.

## Research Methodology
1. **Direct Testing**: Test core functionalities through actual usage
2. **Documentation Review**: Examine official documentation and announcements  
3. **Feature Discovery**: Explore interface elements, menus, and available tools
4. **Limitation Testing**: Identify boundaries and constraints through systematic testing
5. **Comparative Analysis**: Note unique features vs industry standards
6. **Version Tracking**: Document changes from previous assessments

## Research Areas to Cover

### Core Capabilities
- **Text Generation**: Quality, coherence, style adaptability, length handling
- **Reasoning & Analysis**: Logical reasoning, problem decomposition, critical thinking
- **Code Generation**: Programming languages supported, debugging, code explanation
- **Mathematical Problem Solving**: Calculation accuracy, proof generation, statistical analysis
- **Creative Writing**: Fiction, poetry, screenwriting, creative brainstorming
- **Language Understanding**: Translation, multilingual support, context comprehension
- **Information Processing**: Summarization, extraction, synthesis, fact-checking

### Technical Architecture & Features
- **Context Management**: Window size, memory handling, conversation continuity
- **Tool Integration**: Available tools, function calling, external API access
- **File Processing**: Upload types, analysis capabilities, format support
- **Multimodal Capabilities**: Text, image, audio, video processing and generation
- **Real-time Data**: Web search, current information access, live data integration
- **Customization**: System prompts, behavior modification, persona adaptation

### User Interface & Experience
- **Interface Design**: Usability, accessibility, mobile responsiveness
- **Conversation Management**: History, organization, search, export
- **Collaboration Features**: Sharing, team access, workspace management
- **Personalization**: User preferences, learning from interactions
- **Performance**: Response speed, reliability, error handling

### Platform Ecosystem
- **API Access**: Availability, pricing, rate limits, documentation quality
- **Integration Options**: Third-party tools, workflow automation, embeddings
- **Model Variants**: Different models available, specialization, performance tiers
- **Enterprise Features**: Business tools, security, compliance, administration
- **Developer Resources**: SDKs, documentation, community support

### Safety, Ethics & Limitations
- **Content Policies**: Safety filters, refusal patterns, content restrictions
- **Bias & Fairness**: Known biases, mitigation efforts, demographic representation
- **Privacy & Security**: Data handling, retention policies, encryption
- **Transparency**: Model information disclosure, capability explanations
- **Factual Accuracy**: Reliability measures, hallucination rates, citation practices

## Testing Protocols

### Capability Testing Framework
1. **Baseline Tests**: Standard prompts across all platforms for comparison
2. **Edge Case Testing**: Boundary conditions, unusual requests, stress testing
3. **Progressive Complexity**: Simple → complex tasks to identify capability limits
4. **Multi-turn Evaluation**: Conversation coherence and context retention
5. **Domain-Specific Testing**: Specialized knowledge areas and professional use cases

### Documentation Standards
- **Evidence Required**: Screenshots, conversation logs, reproducible examples
- **Confidence Levels**: High/Medium/Low based on testing thoroughness
- **Source Attribution**: Official docs, testing results, user reports, third-party analysis
- **Verification Status**: Confirmed, Partially Verified, Unverified, Disputed
- **Testing Date**: When capability was last verified

## Output Requirements

### YAML Structure Compliance
- Use the provided YAML schema specific to the target platform
- Ensure all required fields are populated with researched data
- Include metadata for tracking updates and versions
- Maintain consistency with existing YAML utilities

### Change Documentation
- Document ALL differences from previous assessment
- Provide specific examples of capability improvements or regressions
- Include dates and version information for changes
- Categorize changes by impact level (Major/Minor/Patch)

### Quality Standards
- **Accuracy**: Verify claims through multiple sources/tests
- **Completeness**: Address all schema sections thoroughly  
- **Objectivity**: Present limitations honestly alongside capabilities
- **Actionability**: Provide enough detail for practical decision-making

## Update Protocol for Living Document

### Version Management
1. **Pre-Update**: Back up current version with timestamp
2. **Research Phase**: Conduct systematic testing using this prompt
3. **Comparison Phase**: Identify all changes from previous version
4. **Documentation Phase**: Update YAML with new findings
5. **Validation Phase**: Cross-check data consistency and format compliance
6. **Publication Phase**: Update version metadata and changelog

### Change Categories
- **New Capabilities**: Previously unavailable features now functional
- **Improved Capabilities**: Existing features with measurable improvements
- **Deprecated Features**: Previously available features no longer accessible
- **Performance Changes**: Speed, accuracy, or reliability modifications
- **Interface Updates**: UI/UX changes affecting user experience
- **Policy Changes**: Modified content policies, usage restrictions, or guidelines

## Platform-Specific Research Focus

### When Researching Claude
- Emphasize Constitutional AI principles and safety measures
- Test Anthropic's specific tools and integrations
- Evaluate reasoning chains and step-by-step analysis
- Assess code generation and artifact creation capabilities

### When Researching ChatGPT  
- Focus on GPT model variants and their differences
- Test OpenAI's plugin ecosystem and tool usage
- Evaluate DALL-E integration and multimodal capabilities
- Assess code interpreter and advanced data analysis features

### When Researching Gemini
- Emphasize Google integration and search capabilities
- Test multimodal input processing (text, image, video)
- Evaluate workspace integration and productivity features
- Assess real-time information access and fact-checking

### When Researching Grok
- Focus on X/Twitter integration and real-time data access
- Test humor and personality in responses
- Evaluate uncensored vs safety-filtered capabilities
- Assess unique xAI architectural features

## Final Deliverable
A comprehensive YAML document following the platform-specific schema that serves as both:
1. **Reference Document**: Complete capability overview for users and developers
2. **Living Document**: Trackable evolution of AI platform capabilities over time

The document should enable stakeholders to make informed decisions about AI platform selection and usage while providing a foundation for ongoing capability monitoring and comparison.