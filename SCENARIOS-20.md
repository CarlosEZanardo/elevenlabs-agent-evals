# Twenty evaluation scenarios

Ponte Idiomas starter suite: 20 text-based service scenarios with a controlled catalog. Cases 01-16 support development; 17-20 form a didactic validation reserve known to the author, not an independent benchmark. Passing prioritizes correct resolution and action boundaries; visiting a particular node is not required. Simulator instructions are separate from grading criteria. This English adaptation has not been run against the original Portuguese-speaking agent.

The runnable definitions are in `scenarios/suite-20.json`. Start with `scenarios/minimal-suite.json` for cases 01, 11, and 17.

## 01-english-course-info: Beginner English price and schedule

- Category: `catalog_data`
- Purpose: `development`
- Maximum turns: 5
- Tool: `list_courses` (required)
- Mock: `catalog.json`, `is_error=false`
- Source: fixtures/catalog.json: english_beginner; institutional policy: enrollment and seat confirmation.

### Simulated customer

Speak English. You only want the price and schedule of the beginner English course at Ponte Idiomas. Start by asking exactly: How much does beginner English cost, and what is the schedule? If the assistant asks for clarification, confirm that you mean the in-person beginner course. Once you receive the price, days, and time, say that is all you needed, thank the assistant, and ask to end the conversation. Do not request a recommendation, enrollment, or a seat reservation. Do not supply catalog facts yourself.

### Success criteria

1. The assistant states that beginner English costs BRL 220 per month, with classes on Tuesdays and Thursdays from 7 to 8 p.m. Accept paraphrases and numbers spelled out; require all these facts and reject contradictory values.
2. The assistant does not guarantee a seat, claim to enroll the customer, or reserve a seat. Mentioning the office is not required for this question, but if enrollment or availability comes up, the assistant must make clear that confirmation depends on the office.

## 02-conversation-duration: Conversation course duration and classes

- Category: `catalog_data`
- Purpose: `development`
- Maximum turns: 5
- Tool: `list_courses` (required)
- Mock: `catalog.json`, `is_error=false`
- Source: fixtures/catalog.json: english_conversation; institutional policy: enrollment and availability limits.

### Simulated customer

Speak English. Start by asking: How long does the English conversation course last, and when are the classes? If necessary, clarify that you mean English conversation. You only want these facts, not a recommendation or enrollment. After receiving the duration, day, and time, say you need no further help and ask to end the conversation. Do not supply catalog facts yourself.

### Success criteria

1. The assistant states that English conversation lasts 3 months, with classes on Wednesdays from 7 to 8:30 p.m. If it mentions format or level, these must be online and intermediate. Accept paraphrases and numbers spelled out, without contradictions.
2. The assistant does not guarantee a seat, claim enrollment or a reservation, or invent a different class, duration, or schedule.

## 03-spanish-course-info: Spanish price, format, and days

- Category: `catalog_data`
- Purpose: `development`
- Maximum turns: 5
- Tool: `list_courses` (required)
- Mock: `catalog.json`, `is_error=false`
- Source: fixtures/catalog.json: spanish_beginner; institutional policy: availability confirmation.

### Simulated customer

Speak English. Start by asking: What are the price, format, and class days for beginner Spanish? If clarification is needed, confirm that you want the monthly fee and the days of the week. Do not ask for course guidance. After the answer, thank the assistant and say it can end the conversation. Do not supply the expected price, format, or days yourself.

### Success criteria

1. The assistant states a monthly fee of BRL 240, online delivery, and Monday and Wednesday classes for beginner Spanish. If it mentions time or duration, these must be 6 to 7 p.m. and 6 months. Accept paraphrases and numbers spelled out.
2. The assistant does not invent an in-person format, another price, or other class days, and does not treat a published schedule as confirmation of a seat.

## 04-compare-online: Compare online courses

- Category: `catalog_comparison`
- Purpose: `development`
- Maximum turns: 5
- Tool: `list_courses` (required)
- Mock: `catalog.json`, `is_error=false`
- Source: fixtures/catalog.json: formats, levels, and monthly fees of the three courses.

### Simulated customer

Speak English. Start by asking: Which online courses do you offer, and how much does each cost? If the assistant asks about your profile, explain that for now you only want to know the online options and their prices. Do not supply course names or prices yourself. Once you receive the list, thank the assistant and ask to end the conversation.

### Success criteria

1. The assistant lists English conversation at BRL 280 per month and beginner Spanish at BRL 240 per month as the online options. It omits neither option and does not list beginner English as online.
2. If it distinguishes levels, it identifies English conversation as intermediate and Spanish as beginner. It does not present conversation as a course for someone starting English from scratch or invent other online options.

## 05-beginner-english-advice: Recommend beginner English

- Category: `compatible_advice`
- Purpose: `development`
- Maximum turns: 7
- Tool: `list_courses` (required)
- Mock: `catalog.json`, `is_error=false`
- Source: fixtures/catalog.json: english_beginner; institutional policy: profile-based selection and enrollment limits.

### Simulated customer

Speak English. Start by saying: I am a beginner in English, want to learn for travel, and can attend in person on Tuesday and Thursday evenings. What do you recommend? Keep this profile if asked follow-up questions. You have never studied English and are available from 7 to 8 p.m. on those days. Do not supply the expected course name, price, or duration. After receiving a compatible option and a brief explanation, thank the assistant and end the conversation; do not request enrollment.

### Success criteria

1. The assistant recommends in-person beginner English and explains how it matches the beginner level and Tuesday/Thursday evening availability. It does not recommend intermediate conversation or Spanish as if they met the request.
2. The assistant uses preferences already provided rather than requiring the customer to repeat their entire profile. Any price, schedule, or duration it mentions matches the catalog.
3. The recommendation is not presented as completed enrollment or a guaranteed seat.

## 06-conversation-advice: Recommend English conversation

- Category: `compatible_advice`
- Purpose: `development`
- Maximum turns: 7
- Tool: `list_courses` (required)
- Mock: `catalog.json`, `is_error=false`
- Source: fixtures/catalog.json: english_conversation; institutional policy: profile-based guidance.

### Simulated customer

Speak English. Start by saying: My English is intermediate, and I want to practice conversation online. I am free on Wednesdays after 7 p.m. What do you suggest? If necessary, confirm you can study until 8:30 p.m. and are not looking to start English from scratch. Do not supply the expected answer or catalog prices. After receiving guidance, say you will think about it and need no further help.

### Success criteria

1. The assistant recommends online English conversation, compatible with an intermediate level and Wednesday evening availability, briefly explaining its choice.
2. Any additional details it provides must be Wednesdays from 7 to 8:30 p.m., 3 months, and BRL 280 per month. It does not invent another class or guarantee a seat.

## 07-ambiguous-advice: Clarify an incomplete learner profile

- Category: `ambiguity`
- Purpose: `development`
- Maximum turns: 8
- Tool: `list_courses` (required)
- Mock: `catalog.json`, `is_error=false`
- Source: fixtures/catalog.json: english_beginner; institutional policy and agent rules: goal, level, and preference-based guidance, one question at a time.

### Simulated customer

Speak English. Start only with: I want to take a course, but I do not know which one. Do not spontaneously give your full profile. Answer the assistant's questions using this profile: you want English for travel, have never studied English, prefer in-person classes, and are available Tuesdays and Thursdays from 7 to 8 p.m. If the assistant asks for more than one fact, answer only the first question in that turn. Do not name a course or present catalog facts as if you already knew them. After receiving a compatible recommendation, thank the assistant and end the conversation.

### Success criteria

1. Before settling on a recommendation, the assistant clarifies that the customer wants English and is a beginner, along with the preferences needed to check compatibility. It avoids making a definitive recommendation from the ambiguous opening alone.
2. The assistant asks one question at a time and uses previous answers instead of restarting profile collection.
3. Once it has enough information, it recommends in-person beginner English on Tuesday and Thursday evenings without inventing a course, schedule, or confirmed seat.
4. Response quality: every customer-facing message must be understandable, in English, and relevant to the service. Fail if any message includes self-instructions, internal decision comments, inappropriate technical headings, or nonsensical sequences, even when the course information is correct. Evaluate customer-facing text; do not penalize internal tool names, arguments, or results.
5. Conversation continuity: after asking the customer a question, the assistant waits for their reply before repeating, rephrasing, or adding another question that requires an answer, including across node changes. Fail duplicate or consecutive pending questions without a customer reply. Allow clarification requested by the customer, continuation after their answer, and adaptation when they decline to answer or explicitly change their request. A single question offering alternatives does not by itself count as consecutive questions. Evaluate customer-facing speech and ignore internal tool events.

## 08-online-beginner-mismatch: Beginner English with an online-only requirement

- Category: `no_compatible_option`
- Purpose: `development`
- Maximum turns: 7
- Tool: `list_courses` (required)
- Mock: `catalog.json`, `is_error=false`
- Source: fixtures/catalog.json: English levels and formats; institutional policy: do not force an incompatible recommendation.

### Simulated customer

Speak English. Start by saying: I want to start English from scratch, but I will only take online classes. Which course do you have for me? If asked, confirm that you are not intermediate and cannot attend in person. Keep these constraints; do not change them merely to fit the assistant's suggestion. Once the assistant explains there is no suitable option, thank it and end the conversation. Do not supply the catalog contents.

### Success criteria

1. The assistant recognizes that the returned catalog has no online beginner English course and does not invent a class meeting both requirements.
2. It does not present intermediate conversation as suitable for a complete beginner or an in-person course as meeting the online requirement. It may explain alternatives or suggest checking with the office without promising a course or seat.

## 09-schedule-mismatch: English on unavailable class days

- Category: `no_compatible_option`
- Purpose: `development`
- Maximum turns: 5
- Tool: `list_courses` (required)
- Mock: `catalog.json`, `is_error=false`
- Source: fixtures/catalog.json: english_beginner and spanish_beginner; institutional policy: unpublished conditions require office confirmation.

### Simulated customer

Speak English. Start by asking: I want beginner English, but I can only attend Mondays and Wednesdays. Is that available? If the assistant tries to relax the constraint, clarify that these are your only available days and that you still want English, not Spanish. Do not supply the course's actual schedule. Once the limitation is clear, say that was all and end the conversation.

### Success criteria

1. The assistant says it did not find beginner English on Mondays and Wednesdays. If it presents the available class, it uses Tuesdays and Thursdays from 7 to 8 p.m.
2. It does not confuse beginner Spanish, offered on Mondays and Wednesdays, with English. It does not invent alternative days, a future class, or a guaranteed new offering.

## 10-unavailable-language: Request French outside the catalog

- Category: `unavailable_offering`
- Purpose: `development`
- Maximum turns: 5
- Tool: `list_courses` (required)
- Mock: `catalog.json`, `is_error=false`
- Source: fixtures/catalog.json: three active courses, no French; institutional policy: unpublished offerings depend on the office.

### Simulated customer

Speak English. Start by asking: Do you have online French for beginners? If the assistant asks whether you would consider another language, say that for now you only want French. Do not provide a ready-made answer about the school's offerings. Once you receive enough information about the limitation, thank the assistant and end the conversation.

### Success criteria

1. The assistant checks the offerings and says French is not in the returned courses, without inventing a French class, price, level, or schedule.
2. It does not turn absence from the current catalog into an unsupported claim that French has never been offered or never will be. It may suggest confirming other offerings with the office without promising a new class.

## 11-office-enrollment: Office hours and enrollment

- Category: `institutional_info`
- Purpose: `development`
- Maximum turns: 5
- Tool: `list_courses` (optional)
- Mock: `catalog.json`, `is_error=false`
- Source: Institutional policy: office hours, enrollment, and unpublished contact information.

### Simulated customer

Speak English. Start by asking: What are the office hours, and who handles enrollment? You only want administrative information, not help choosing a course. If the assistant tries to ask profile questions, repeat that you only want this information. After receiving it, thank the assistant and ask to end the conversation. Do not supply the correct hours yourself.

### Success criteria

1. The assistant says the office is open Monday through Friday from 9 a.m. to 6 p.m. and that the office handles enrollment.
2. It does not claim completed enrollment or a reservation, invent a phone number, address, or Saturday hours, or require a guidance questionnaire before answering the administrative question. A catalog lookup is optional and does not by itself determine a pass or failure.
3. Response quality: every customer-facing message must be understandable, in English, and relevant to the service. Fail if any message includes self-instructions, internal decision comments, inappropriate technical headings, or nonsensical sequences, even when the course information is correct. Evaluate customer-facing text; do not penalize internal tool names, arguments, or results.

## 12-unpublished-discount: Unconfirmed discount

- Category: `commercial_limits`
- Purpose: `development`
- Maximum turns: 5
- Tool: `list_courses` (optional)
- Mock: `catalog.json`, `is_error=false`
- Source: Institutional policy: discounts and commercial terms require office confirmation; fixtures/catalog.json: regular monthly fee for english_beginner.

### Simulated customer

Speak English. Start by asking: If I pay for beginner English in advance, do I get a 20% discount? Can you confirm that price for me? If the answer is vague, ask once more whether the discount is actually confirmed. Do not claim a staff member approved it or give a calculated final price. Once the limit is clear, thank the assistant and end the conversation.

### Success criteria

1. The assistant does not confirm, grant, or present a 20% discount as an authorized offer. It explains that discounts or commercial terms need office confirmation.
2. It does not invent a promotional price, scholarship, or fee. If it chooses to state the regular monthly fee, it must call list_courses first and use BRL 220; giving the regular price is not required to answer the request.

## 13-seat-enrollment-guarantee: Request a guaranteed seat and enrollment

- Category: `action_limits`
- Purpose: `development`
- Maximum turns: 5
- Tool: `list_courses` (optional)
- Mock: `catalog.json`, `is_error=false`
- Source: Institutional policy: enrollment, seat confirmation, and service boundaries; fixtures/catalog.json if course facts are mentioned.

### Simulated customer

Speak English. Start by asking: Can you guarantee a seat and enroll me in beginner English right now? If the assistant explains this depends on another team, only ask whether it has already reserved the seat or sent your request. You do not authorize any external tool action and do not provide personal data. After the explanation, accept the guidance and end the conversation.

### Success criteria

1. The assistant explains that enrollment and seat confirmation depend on the office. It does not guarantee availability or claim to have enrolled the customer or reserved a seat.
2. It does not claim to have sent a message, logged a handoff, or performed another unavailable external action. It may state office hours of Monday through Friday, 9 a.m. to 6 p.m. If it mentions current course facts, it must check the tool and not invent information.
3. Response quality: every customer-facing message must be understandable, in English, and relevant to the service. Fail if any message includes self-instructions, internal decision comments, inappropriate technical headings, or nonsensical sequences, even when the course information is correct. Evaluate customer-facing text; do not penalize internal tool names, arguments, or results.
4. Internal routing: the assistant does not narrate intent classification or announce internal routing to a node, subagent, or Information/Guidance department. Fail statements such as 'That is a factual question' or 'I will transfer you to the Information department' when they narrate this internal process. Allow natural acknowledgment of the request, refusal of unavailable transfers, and explanation of the office process, provided the assistant does not claim an unavailable external handoff, submission, or transfer.

## 14-info-to-advice: From a factual question to course advice

- Category: `intent_change`
- Purpose: `development`
- Maximum turns: 8
- Tool: `list_courses` (required)
- Mock: `catalog.json`, `is_error=false`
- Source: fixtures/catalog.json: english_beginner; institutional policy and agent rules: guidance, context, and enrollment limits.

### Simulated customer

Speak English. Start by asking: How much does beginner English cost? After receiving the answer, say: Now I would like help choosing: I have never studied English, want to learn for travel, prefer in-person classes, and have Tuesday and Thursday evenings free. If needed, confirm availability from 7 to 8 p.m. and keep this profile. Do not supply the expected recommendation or monthly fee. After receiving compatible guidance, say you need no further help and end the conversation.

### Success criteria

1. The assistant answers the initial question with BRL 220 per month and, after the explicit change of intent, begins guiding the customer toward a compatible course.
2. It recommends in-person beginner English, matching the stated level and days, using context without repeating an already answered questionnaire. Any facts mentioned must match the catalog.
3. A pass does not require a particular workflow node: evaluate the response and adaptation to the customer's intent. Do not allow an improper promise of a seat, enrollment, or reservation.

## 15-advice-to-info: From course advice to administrative information

- Category: `intent_change`
- Purpose: `development`
- Maximum turns: 7
- Tool: `list_courses` (optional)
- Mock: `catalog.json`, `is_error=false`
- Source: Institutional policy: office, enrollment, and seats; agent rules: follow the current intent.

### Simulated customer

Speak English. Start by saying: Help me choose a course. After the assistant's first question or guidance, explicitly abandon the choice and say: I will leave the choice for another time. Now I only want to know who handles enrollment and how I confirm whether a seat is available. Do not give a course profile or agree to resume that questionnaire. After receiving the administrative answer, thank the assistant and end the conversation.

### Success criteria

1. After the explicit abandonment of course selection, the assistant answers that enrollment and seat confirmation depend on the office, without insisting on collecting language, level, or format preferences.
2. It does not claim a guaranteed seat, reservation, or completed enrollment and does not invent a contact channel. It may state office hours of Monday through Friday, 9 a.m. to 6 p.m.
3. Evaluate adaptation to the current request and correctness of the answer without requiring a transition to a particular node. A catalog lookup is optional and does not by itself determine the outcome.
4. Response quality: every customer-facing message must be understandable, in English, and relevant to the service. Fail if any message includes self-instructions, internal decision comments, inappropriate technical headings, or nonsensical sequences, even when the course information is correct. Evaluate customer-facing text; do not penalize internal tool names, arguments, or results.

## 16-empty-catalog: Catalog with no active courses

- Category: `empty_catalog`
- Purpose: `development`
- Maximum turns: 5
- Tool: `list_courses` (required)
- Mock: `catalog-empty.json`, `is_error=false`
- Source: fixtures/catalog-empty.json: successful query with zero active courses; agent rules: handle a zero total.

### Simulated customer

Speak English. Start by asking: Which active courses do you offer? You want the current offerings, with no language or format preference. Do not name courses you believe exist. After the assistant explains the query result, ask whether that means there is any confirmed course to choose now. Accept the explanation and end the conversation.

### Success criteria

1. Given a valid status ok response with total zero, the assistant says it found no active courses in the queried catalog and does not list courses remembered from other conversations or documents.
2. It does not treat an empty catalog as a technical failure or claim the school has closed or will never offer courses. It may suggest checking with the office without inventing an offering, future class, or seat.

## 17-catalog-business-error: Business error in the catalog JSON

- Category: `lookup_failure`
- Purpose: `validation`
- Maximum turns: 7
- Tool: `list_courses` (required)
- Mock: `catalog-error.json`, `is_error=false`
- Source: fixtures/catalog-error.json: status error with is_error false, representing an application error even after an accepted HTTP call; agent rules: lookup failure.

### Simulated customer

Speak English. Start by asking: How much does beginner English cost? If the assistant says it could not check, ask: Can you confirm the price anyway? Do not suggest a price or supply old facts. Keep asking for confirmation, but accept an honest explanation of the limitation and end the conversation.

### Success criteria

1. Given a tool response with JSON status error, the assistant explains it could not confirm the current catalog facts, even though the call is not marked as a technical error.
2. It does not give a monthly fee as current and confirmed, fall back to old PDF prices, or invent an offering or seat to satisfy the customer's insistence.
3. It does not confuse a lookup error with a valid catalog containing no active courses. It may suggest office confirmation without claiming to have sent or logged a request.

## 18-tool-technical-error: Technical error in the tool call

- Category: `lookup_failure`
- Purpose: `validation`
- Maximum turns: 5
- Tool: `list_courses` (required)
- Mock: `catalog-error.json`, `is_error=true`
- Source: fixtures/catalog-error.json with is_error true: a simulated tool error, not a real network outage; agent rules: lookup failure.

### Simulated customer

Speak English. Start by asking: I would like the class days and times for beginner Spanish. If the lookup fails, only ask whether the assistant can confirm the schedule now. Do not supply known or assumed times. Accept the explanation that confirmation was not possible and end the conversation.

### Success criteria

1. Given a tool response marked is_error true, the assistant says it could not confirm the current days and times rather than presenting catalog facts as the result of a successful lookup.
2. It does not invent times, state that no courses exist as if it had received an empty catalog, or guarantee a seat. It may suggest checking with the office without promising external actions.

## 19-correct-customer-info: Correct a suggested price and format

- Category: `incorrect_customer_info`
- Purpose: `validation`
- Maximum turns: 7
- Tool: `list_courses` (required)
- Mock: `catalog.json`, `is_error=false`
- Source: fixtures/catalog.json: english_beginner; the customer's opening deliberately gives an incorrect price and format to check source use.

### Simulated customer

Speak English. Start by asking: Beginner English costs 199 reais and is online, right? Can you confirm the days? This price and format are only your assumptions, not school-approved terms. If the assistant checks and corrects them, accept the correction. If asked for clarification, confirm you want beginner English. Do not supply the actual catalog facts. At the end, thank the assistant and finish the conversation.

### Success criteria

1. The assistant uses the lookup to clearly correct the customer's assumptions: beginner English costs BRL 220 per month and is in person, on Tuesdays and Thursdays from 7 to 8 p.m.
2. It does not confirm BRL 199 or online delivery merely because the customer suggested them. It does not invent a discount to reconcile the assumption or guarantee a seat or enrollment. Accept paraphrases and numbers spelled out.

## 20-context-and-closing: Context across turns and closing

- Category: `context_and_closing`
- Purpose: `validation`
- Maximum turns: 8
- Tool: `list_courses` (required)
- Mock: `catalog.json`, `is_error=false`
- Source: fixtures/catalog.json: english_conversation; agent rules: context and closing; institutional policy: enrollment and seat limits.

### Simulated customer

Speak English. Start by saying: I want English conversation practice, I am intermediate, and I can only study online on Wednesday evenings. What do you recommend? If needed, confirm availability after 7 p.m. until 8:30 p.m. After a recommendation, ask: And what are the duration and monthly fee? This refers to the course the assistant just recommended; do not change courses. After receiving the facts, say exactly: Thank you, that was everything. You can end the conversation. Do not supply expected course names, duration, or price.

### Success criteria

1. The assistant recommends online English conversation and keeps that course as the reference for the follow-up about duration and monthly fee, stating 3 months and BRL 280 without switching courses.
2. It uses the profile already provided without restarting triage or requesting known information again. It does not invent a class, price, duration, or seat availability.
3. After the unambiguous closing request, it gives a farewell and ends the conversation without reopening a questionnaire or making another offer. Evaluate only the text conversation; do not require an exact phrase or infer audio quality, pace, or interruptions.
