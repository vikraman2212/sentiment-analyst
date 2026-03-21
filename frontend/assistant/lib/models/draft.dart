class Draft {
  final String draftId;
  final String clientName;
  final String triggerType;
  final String generatedContent;
  final String contextUsed;

  const Draft({
    required this.draftId,
    required this.clientName,
    required this.triggerType,
    required this.generatedContent,
    required this.contextUsed,
  });

  factory Draft.fromJson(Map<String, dynamic> json) => Draft(
        draftId: json['draft_id'] as String,
        clientName: json['client_name'] as String,
        triggerType: json['trigger_type'] as String,
        generatedContent: json['generated_content'] as String,
        contextUsed: json['context_used'] as String,
      );

  Map<String, dynamic> toJson() => {
        'draft_id': draftId,
        'client_name': clientName,
        'trigger_type': triggerType,
        'generated_content': generatedContent,
        'context_used': contextUsed,
      };
}
