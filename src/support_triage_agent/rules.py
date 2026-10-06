"""Plain rules that read the ticket before and after the model.

Hard rules run first. A hit on any of them holds the ticket for a person, and the model is never asked:
legal threats, data-protection requests, suspected fraud, safety hazards, and messages that try to give
the agent instructions.

Problem signals run when the model wants to close a ticket. They spot words that mean a person has to
fix something (a double charge, a cracked table top, an error message). A signal can stop a close; it can
never force one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SAME_SENTENCE = r"[^.?!\n]{0,40}"


def _patterns(*sources: str) -> list[re.Pattern]:
    return [re.compile(source.replace("{S}", _SAME_SENTENCE), re.IGNORECASE) for source in sources]


HARD_RULES: dict[str, list[re.Pattern]] = {
    "legal": _patterns(
        r"\b(?:lawyer|solicitor|attorney|barrister|legal counsel)s?\b",
        r"\blegal (?:action|steps|proceedings|advice|claim)\b",
        r"\bsmall[- ]claims\b",
        r"\b(?:to|in|before) court\b",
        r"\bcourt (?:case|action|claim|order)\b",
        r"\b(?:will|going to|gonna|shall|i'll|to) sue\b",
        r"\bsuing\b",
        r"\bconsumer (?:protection|authority|authorities|ombudsman|rights (?:body|organisation|organization))\b",
        r"\bombudsman\b",
        r"\btrading standards\b",
        r"\bfil(?:e|ed|ing) (?:a )?(?:claim|complaint|lawsuit|case) against\b",
        r"\bmy (?:legal |statutory )?rights as a consumer\b",
    ),
    "data_protection": _patterns(
        r"\b(?:GDPR|DSGVO|RGPD)\b",
        r"\bright to (?:be forgotten|erasure|access)\b",
        r"\bsubject access request\b",
        r"\bdata protection\b",
        r"\b(?:delete|erase|remove|wipe|destroy)\w*\b{S}\b(?:personal (?:data|information|details)"
        r"|my (?:data|information|personal|details|account|profile)"
        r"|all (?:of )?(?:my|the) (?:data|information|details))\b",
        r"\b(?:everything|all (?:of )?(?:the )?(?:data|information)) you (?:hold|have|store|keep) (?:about|on) me\b",
        r"\b(?:don't|do not|no longer) want\b{S}\b(?:keep|store|hold|retain|have)\b{S}\b(?:my|about me)\b",
        r"\bnothing about me\b",
    ),
    "fraud": _patterns(
        r"\b(?:never|didn't|did not|haven't|have not)\s+(?:place|placed|make|made|order|ordered|authori[sz]ed?)\b"
        r"[^.?!\n]{0,30}\b(?:this|that|these|the|an?|any) (?:order|purchase|payment|transaction)s?\b",
        r"\b(?:orders?|purchases?|payments?)\b[^.?!\n]{0,20}\b(?:I|we) (?:never|didn't|did not) "
        r"(?:place|placed|make|made|order|ordered)\b",
        r"\b(?:don't|do not|didn't|did not) recogni[sz]e\b[^.?!\n]{0,30}"
        r"\b(?:order|payment|charge|transaction|purchase)s?\b",
        r"\b(?:someone|somebody|a stranger)\b[^.?!\n]{0,30}\b(?:used|using|has used|got into|accessed)\b"
        r"[^.?!\n]{0,20}\b(?:card|account|details|identity)\b",
        r"\b(?:hacked|compromised)\b",
        r"\b(?:card|identity|details|password) (?:was|were|has been|got) stolen\b",
        r"\bunauthori[sz]ed (?:payment|charge|transaction|order|purchase)s?\b",
        r"\b(?:fraud|fraudulent|identity theft|phishing)\b",
        r"\b(?:that|this|it)(?:'s| is| was) not me\b",
        r"\bnot my address\b",
        r"\b(?:haven't|have not|never|didn't|did not) (?:ever )?(?:bought|ordered|purchased) anything\b",
    ),
    "safety": _patterns(
        r"\bspark(?:s|ed|ing)?\b",
        r"\b(?:caught|catch|catching|on) fire\b",
        r"\bflames?\b",
        r"\bburning smell\b",
        r"\bsmell(?:s|ed)? (?:of |like )?(?:it'?s )?burning\b",
        r"\b(?:started|began) (?:to )?smok(?:e|ing)\b",
        r"\bsmoke (?:came|was coming|is coming|coming|poured)\b",
        r"\bwas smoking\b",
        r"\belectric(?:al)? shock\b",
        r"\b(?:lamp|plug|socket|cable|wire|switch|bulb|charger)\b[^.?!\n]{0,30}\bshock",
        r"\boverheat\w*\b",
        r"\bmelt(?:s|ed|ing)?\b",
        r"\binjur(?:y|ies|ed|e)\b",
        r"\bhurt (?:myself|himself|herself|themselves|my|his|her|their)\b",
        r"\bcut (?:my|his|her|their) (?:hand|finger|arm|leg|foot|feet|head|face)\b",
        r"\bbleeding\b",
        r"\b(?:tipped|toppled|fell|collapsed|came down)\b[^.?!\n]{0,30}\b(?:on|onto|over|on top of)\b"
        r"[^.?!\n]{0,20}\b(?:me|my|him|her|us|them|child|children|son|daughter|baby|kids?|toddler|dog|cat)\b",
        r"\bcame (?:away|off|loose) from the wall\b",
        r"\bcrashed down\b",
        r"\b(?:fire|safety|electrical|choking) hazard\b",
        r"\bunsafe\b",
        r"\bdangerous\b",
    ),
    "injection": _patterns(
        r"\b(?:ignore|disregard|forget|override|bypass)\b[^.?!\n]{0,30}"
        r"\b(?:instructions?|rules|guidelines|polic(?:y|ies)|prompt|programming|restrictions)\b",
        r"\byou are now (?:a|an|in|the|my)\b",
        r"\b(?:pretend|imagine) (?:to be|you are|you're)\b",
        r"\b(?:act|behave) as (?:if you were |though you were )?(?:a|an|my|the) (?:\w+ )?"
        r"(?:bot|assistant|agent|ai|admin|administrator|manager|system)\b",
        r"\b(?:system|developer|admin|god|debug|maintenance) (?:mode|prompt|override|message|instructions?)\b",
        r"\bjailbreak\w*\b",
        r"\bas an? (?:ai|artificial intelligence|language model|llm|chatbot|bot)\b",
        r"\b(?:new|updated) instructions?\b",
        r"\b(?:do not|don't|never) (?:escalate|route|forward|pass|send|hand)\b[^.?!\n]{0,30}"
        r"\b(?:humans?|person|people|staff|managers?|supervisors?|colleagues?)\b",
        r"<\s*/?\s*(?:system|instructions?)\s*>",
        r"\[/?INST\]",
        r"\b(?:to|for) the (?:ai|bot|chatbot|automated (?:assistant|agent|system))\b",
        r"\b(?:note|message|instructions?) (?:for|to) (?:the )?(?:automated|ai|support|virtual) "
        r"(?:assistant|agent|bot|system)\b",
        r"\b(?:new|updated|revised) (?:policy|rules|instructions) (?:is|are) that\b",
        r"\b(?:reply|respond|answer) only with\b",
    ),
}

PROBLEM_SIGNALS: dict[str, list[re.Pattern]] = {
    "billing": _patterns(
        r"\b(?:charged|billed|debited|paid|taken|took|deducted)\b[^.?!\n]{0,25}\b(?:twice|two times|double)\b",
        r"\bdouble[- ](?:charged?|payment|billed|debit)\b",
        r"\b(?:two|2|duplicate|double) (?:identical )?(?:payments|charges|debits|transactions)\b",
        r"\b(?:reminder|late|admin|administration) fee\b",
        r"\breminder\b{S}\bfee\b",
        r"\balready paid\b",
        r"\bprice\b[^.?!\n]{0,30}\b(?:dropped|went down|has gone down|is now lower|reduced|lowered|cheaper)\b",
        r"\b(?:cheaper|on sale|reduced) (?:now|since|today|this week)\b",
        r"\bprice (?:drop|difference)\b",
        r"\bnow\b{S}\binstead of\b",
        r"\b(?:get|pay|refund)\b{S}\bdifference\b",
        r"\b(?:add|change|correct|put|include|amend|update)\b{S}\b(?:VAT (?:number|ID)|company name|company details"
        r"|business name)\b",
        r"\b(?:wrong|incorrect)\b[^.?!\n]{0,20}\b(?:invoice|VAT number|company name|amount charged)\b",
        r"\b(?:our|my|the company'?s?) VAT (?:number|ID)\b",
        r"\bin the name of\b",
        r"\bcompany (?:details|name)\b",
    ),
    "logistics": _patterns(
        r"\b(?:damaged|broken|cracked|scratched|dented|smashed|shattered|chipped|ripped)\b",
        r"\b(?:chip|chips|scratch|scratches|dent|dents)\b",
        r"\ba (?:tear|hole|crack|dent) in\b",
        r"\b(?:sent|send|received|delivered|shipped|arrived with|came with|gave me|got)\b[^.?!\n]{0,30}\bwrong\b",
        r"\bwrong (?:item|colou?r|product|model)\b",
        r"\b(?:contained|received|sent me|got)\b[^.?!\n]{0,40}\binstead of\b",
        r"\b(?:isn't|is not|wasn't|was not|not) what I ordered\b",
        r"\bmissing (?:parts?|screws?|bolts?|pieces?|fittings?|legs?|hardware|components?|dowels?)\b",
        r"\b(?:parts?|screws?|bolts?|pieces?|fittings?|legs?|dowels?)\b(?! of (?:my|the|our) (?:order|delivery|parcel))"
        r"[^.?!\n]{0,20}\b(?:are|is|were|was) missing\b",
        r"\bparts? missing\b",
        r"\b(?:screws?|bolts?|hinges?|shelf pins|handles?|dowels?|fittings?|legs?|part \d+)\b{S}"
        r"\b(?:missing|not in the (?:box|package|pack))\b",
        r"\bincomplete (?:box|package|kit|set)\b",
        r"\bcan(?:'t|not) (?:finish|complete) (?:building|assembling|it)\b",
        r"\b(?:didn't|did not|never|failed to) (?:show up|turn up|show|collect|pick up|pick it up)\b",
        r"\bno[- ]show\b",
        r"\b(?:nobody|no one|no-one) (?:came|showed up|turned up|arrived|collected)\b",
        r"\b(?:not|never) (?:been )?(?:collected|picked up)\b",
        r"\b(?:hasn't|has not|haven't|have not|wasn't|was not|weren't|were not) (?:yet )?(?:been )?"
        r"(?:collected|picked up)\b",
        r"\bnever happened\b",
        r"\b(?:parcel|package|delivery|order)\b[^.?!\n]{0,12}\b(?:is |was |got |seems )?(?:lost|stuck)\b",
        r"\btracking\b{S}\b(?:hasn't|has not|not) (?:changed|moved|updated)\b",
    ),
    "tech": _patterns(
        r"\berror\b",
        r"\bcrash(?:es|ed|ing)?\b",
        r"\b(?:bug|glitch)\b",
        r"\b(?:blank|white|empty) (?:page|screen)\b",
        r"\bpage (?:stays|is|goes|went) (?:blank|white|empty)\b",
        r"\b(?:won't|doesn't|does not|will not|wouldn't|didn't) (?:load|open)\b",
        r"\bkeeps? (?:crashing|freezing|logging me out|failing|spinning|loading)\b",
        r"\bsomething went wrong\b",
        r"\blink\b{S}\b(?:expired|invalid|not valid|no longer valid|broken|dead|doesn't work|does not work)\b",
        r"\binvalid\b",
        r"\bsession (?:has )?expired\b",
        r"\bcan(?:'t|not) (?:pay|check ?out|reset|place (?:my|an|the) order)\b",
        r"\bproblem placing\b",
        r"\bcan(?:'t|not) (?:change|update) my (?:e-?mail|details)\b",
        r"\b(?:doesn't|does not|won't|will not|didn't|did not) save\b",
        r"\bjust reloads\b",
        r"\bapp\b{S}\b(?:closes|shuts down|quits|freezes)\b",
        r"\breset\b{S}\b(?:doesn't|does not|won't|didn't|did not) work\b",
        r"\b(?:payment|checkout|page|site|website|app)\b[^.?!\n]{0,20}\b(?:fails|failed|failing|times out|timed out"
        r"|not working|isn't working|doesn't work|does not work|stopped working)\b",
    ),
}

RULE_LABELS = {
    "legal": "legal threat",
    "data_protection": "data-protection request",
    "fraud": "possible fraud",
    "safety": "safety risk",
    "injection": "instructions aimed at the agent",
    "billing": "billing problem",
    "logistics": "delivery or product problem",
    "tech": "technical problem",
}


@dataclass(frozen=True)
class Hit:
    rule: str
    phrase: str


def _first_hits(text: str, rules: dict[str, list[re.Pattern]]) -> list[Hit]:
    hits = []
    for rule, patterns in rules.items():
        matches = [match for pattern in patterns if (match := pattern.search(text))]
        if matches:
            first = min(matches, key=lambda match: (match.start(), -match.end()))
            hits.append(Hit(rule, re.sub(r"\s+", " ", first.group(0)).strip()))
    return hits


def hard_rules(text: str) -> list[Hit]:
    """Reasons a person must handle this ticket. Any hit holds it, whatever the model would say."""
    return _first_hits(text, HARD_RULES)


def problem_signals(text: str) -> list[Hit]:
    """Words that mean a person has to fix something. The rule name is the team that usually fixes it."""
    return _first_hits(text, PROBLEM_SIGNALS)


def describe_hits(hits: list[Hit]) -> str:
    return "; ".join(f'{RULE_LABELS[hit.rule]} ("{hit.phrase}")' for hit in hits)
