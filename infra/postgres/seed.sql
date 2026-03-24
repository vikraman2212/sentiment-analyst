-- =============================================================================
-- Seed data for local / CI development
-- Run via `make seed-db` after migrations have been applied.
-- Safe to re-run: all inserts are guarded with ON CONFLICT DO NOTHING.
-- =============================================================================

-- Required ENUMs and tables must already exist (created by Alembic migrations).
-- This script assumes `alembic upgrade head` (or `make stack-migrate`) has
-- already been executed against the target database.

-- -----------------------------------------------------------------------------
-- ADVISORS  (2 advisors)
-- -----------------------------------------------------------------------------
INSERT INTO advisor (id, full_name, email, default_tone) VALUES
  ('a1000000-0000-0000-0000-000000000001', 'Sarah Mitchell',  'sarah.mitchell@wealthfirm.com',  'empathetic'),
  ('a1000000-0000-0000-0000-000000000002', 'James Thornton',  'james.thornton@wealthfirm.com',  'professional')
ON CONFLICT DO NOTHING;

-- -----------------------------------------------------------------------------
-- CLIENTS  (5 per advisor = 10 total)
-- -----------------------------------------------------------------------------
INSERT INTO client (id, advisor_id, first_name, last_name, next_review_date) VALUES
  -- Sarah Mitchell's clients
  ('c1000000-0000-0000-0000-000000000001', 'a1000000-0000-0000-0000-000000000001', 'Oliver',   'Bennett',    '2025-09-15'),
  ('c1000000-0000-0000-0000-000000000002', 'a1000000-0000-0000-0000-000000000001', 'Priya',    'Mehta',      '2025-07-22'),
  ('c1000000-0000-0000-0000-000000000003', 'a1000000-0000-0000-0000-000000000001', 'Thomas',   'Nguyen',     '2025-11-03'),
  ('c1000000-0000-0000-0000-000000000004', 'a1000000-0000-0000-0000-000000000001', 'Amelia',   'Okafor',     '2025-08-30'),
  ('c1000000-0000-0000-0000-000000000005', 'a1000000-0000-0000-0000-000000000001', 'Daniel',   'Kowalski',   '2026-01-10'),
  -- James Thornton's clients
  ('c1000000-0000-0000-0000-000000000006', 'a1000000-0000-0000-0000-000000000002', 'Sofia',    'Andersen',   '2025-10-05'),
  ('c1000000-0000-0000-0000-000000000007', 'a1000000-0000-0000-0000-000000000002', 'Marcus',   'Silva',      '2025-06-18'),
  ('c1000000-0000-0000-0000-000000000008', 'a1000000-0000-0000-0000-000000000002', 'Yuki',     'Tanaka',     '2025-12-01'),
  ('c1000000-0000-0000-0000-000000000009', 'a1000000-0000-0000-0000-000000000002', 'Rachel',   'O''Brien',   '2026-02-14'),
  ('c1000000-0000-0000-0000-000000000010', 'a1000000-0000-0000-0000-000000000002', 'Ethan',    'Patel',      '2025-05-28')
ON CONFLICT DO NOTHING;

-- -----------------------------------------------------------------------------
-- FINANCIAL PROFILES  (one per client)
-- -----------------------------------------------------------------------------
INSERT INTO financial_profile (id, client_id, total_aum, ytd_return_pct, risk_profile) VALUES
  ('f1000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001',  850000.00,   6.240, 'moderate'),
  ('f1000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000002', 1250000.00,   8.750, 'aggressive'),
  ('f1000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000003',  420000.00,   3.100, 'conservative'),
  ('f1000000-0000-0000-0000-000000000004', 'c1000000-0000-0000-0000-000000000004', 2100000.00,  11.320, 'aggressive'),
  ('f1000000-0000-0000-0000-000000000005', 'c1000000-0000-0000-0000-000000000005',  675000.00,   5.480, 'moderate'),
  ('f1000000-0000-0000-0000-000000000006', 'c1000000-0000-0000-0000-000000000006',  320000.00,   2.750, 'conservative'),
  ('f1000000-0000-0000-0000-000000000007', 'c1000000-0000-0000-0000-000000000007', 3450000.00,  14.900, 'aggressive'),
  ('f1000000-0000-0000-0000-000000000008', 'c1000000-0000-0000-0000-000000000008',  980000.00,   7.620, 'moderate'),
  ('f1000000-0000-0000-0000-000000000009', 'c1000000-0000-0000-0000-000000000009',  545000.00,   4.330, 'moderate'),
  ('f1000000-0000-0000-0000-000000000010', 'c1000000-0000-0000-0000-000000000010', 1780000.00,  -1.150, 'conservative')
ON CONFLICT DO NOTHING;

-- -----------------------------------------------------------------------------
-- INTERACTIONS  (2 per client = 20 total)
-- -----------------------------------------------------------------------------
INSERT INTO interaction (id, client_id, type, raw_transcript, audio_file_key, created_at) VALUES
  -- Oliver Bennett
  ('b1000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001', 'voice_memo',
   'Oliver mentioned he is planning to retire in 10 years and wants to start shifting to lower risk assets. He also said his son just started university.',
   NULL, '2025-03-01 09:15:00+00'),
  ('b1000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000001', 'voice_memo',
   'Follow-up call: Oliver is concerned about recent market volatility. He asked about moving a portion into bonds. Mentioned family holiday to Italy in June.',
   NULL, '2025-03-10 11:00:00+00'),

  -- Priya Mehta
  ('b1000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000002', 'voice_memo',
   'Priya is very interested in ESG investing. She has a high risk tolerance and wants to maximise long-term growth. She runs her own tech consultancy.',
   NULL, '2025-02-14 14:30:00+00'),
  ('b1000000-0000-0000-0000-000000000004', 'c1000000-0000-0000-0000-000000000002', 'voice_memo',
   'Priya asked about sector rotation into AI-related stocks. She also mentioned she is expecting a large bonus payout in Q3 and wants to invest it.',
   NULL, '2025-03-05 10:45:00+00'),

  -- Thomas Nguyen
  ('b1000000-0000-0000-0000-000000000005', 'c1000000-0000-0000-0000-000000000003', 'voice_memo',
   'Thomas is very risk averse. He is close to retirement and wants capital preservation above all. He expressed worry about inflation eating into his savings.',
   NULL, '2025-01-20 16:00:00+00'),
  ('b1000000-0000-0000-0000-000000000006', 'c1000000-0000-0000-0000-000000000003', 'voice_memo',
   'Thomas reviewed his fixed income holdings. He is happy with current bond allocation but wants more information on TIPS. Wife recently diagnosed with illness - additional cost concerns.',
   NULL, '2025-02-28 09:30:00+00'),

  -- Amelia Okafor
  ('b1000000-0000-0000-0000-000000000007', 'c1000000-0000-0000-0000-000000000004', 'voice_memo',
   'Amelia is an entrepreneur with strong cash flows. She wants to diversify into real estate investment trusts. Her business just completed a Series B funding round.',
   NULL, '2025-03-12 13:00:00+00'),
  ('b1000000-0000-0000-0000-000000000008', 'c1000000-0000-0000-0000-000000000004', 'voice_memo',
   'Amelia is interested in private equity opportunities. She mentioned wanting to set up a family trust for estate planning purposes.',
   NULL, '2025-03-19 15:30:00+00'),

  -- Daniel Kowalski
  ('b1000000-0000-0000-0000-000000000009', 'c1000000-0000-0000-0000-000000000005', 'voice_memo',
   'Daniel recently moved to Australia from Poland. He is building his portfolio from scratch and wants a balanced approach. He is keen on international diversification.',
   NULL, '2025-03-08 10:00:00+00'),
  ('b1000000-0000-0000-0000-000000000010', 'c1000000-0000-0000-0000-000000000005', 'voice_memo',
   'Daniel asked about currency hedging strategies given his income is partly in EUR. He also expressed interest in index funds for long-term retirement savings.',
   NULL, '2025-03-15 14:00:00+00'),

  -- Sofia Andersen
  ('b1000000-0000-0000-0000-000000000011', 'c1000000-0000-0000-0000-000000000006', 'voice_memo',
   'Sofia is a school teacher approaching retirement. She wants steady income and is interested in dividend-paying stocks and term deposits.',
   NULL, '2025-01-15 09:00:00+00'),
  ('b1000000-0000-0000-0000-000000000012', 'c1000000-0000-0000-0000-000000000006', 'voice_memo',
   'Sofia mentioned she is planning to downsize her home next year. Proceeds from the sale should be reinvested. She is also concerned about aged care costs in future.',
   NULL, '2025-02-20 11:15:00+00'),

  -- Marcus Silva
  ('b1000000-0000-0000-0000-000000000013', 'c1000000-0000-0000-0000-000000000007', 'voice_memo',
   'Marcus is a high-net-worth individual who runs a logistics firm. He is comfortable with high risk and wants aggressive growth. Has a strong interest in emerging markets.',
   NULL, '2025-02-05 15:00:00+00'),
  ('b1000000-0000-0000-0000-000000000014', 'c1000000-0000-0000-0000-000000000007', 'voice_memo',
   'Marcus reviewed his emerging market exposure. He asked about adding cryptocurrency as a small speculative allocation. He mentioned upcoming travel to Brazil for business.',
   NULL, '2025-03-03 13:30:00+00'),

  -- Yuki Tanaka
  ('b1000000-0000-0000-0000-000000000015', 'c1000000-0000-0000-0000-000000000008', 'voice_memo',
   'Yuki is a software engineer in her mid-30s with a long investment horizon. She wants a growth-oriented portfolio with some tech sector weighting.',
   NULL, '2025-02-10 10:30:00+00'),
  ('b1000000-0000-0000-0000-000000000016', 'c1000000-0000-0000-0000-000000000008', 'voice_memo',
   'Yuki mentioned she is planning to buy an investment property in 3 years and needs liquidity planning around that goal.',
   NULL, '2025-03-18 16:00:00+00'),

  -- Rachel O'Brien
  ('b1000000-0000-0000-0000-000000000017', 'c1000000-0000-0000-0000-000000000009', 'voice_memo',
   'Rachel is a GP with a stable high income. She wants to minimise tax exposure through salary sacrifice and off-market investments. She prefers ethical investing.',
   NULL, '2025-01-28 08:45:00+00'),
  ('b1000000-0000-0000-0000-000000000018', 'c1000000-0000-0000-0000-000000000009', 'voice_memo',
   'Rachel reviewed her superannuation strategy. She wants to maximise concessional contributions. She mentioned a potential career move to a private practice.',
   NULL, '2025-03-06 12:00:00+00'),

  -- Ethan Patel
  ('b1000000-0000-0000-0000-000000000019', 'c1000000-0000-0000-0000-000000000010', 'voice_memo',
   'Ethan is a recently retired banker. He wants income-generating assets to supplement his pension. He is moderately conservative and dislikes volatility.',
   NULL, '2025-01-10 10:00:00+00'),
  ('b1000000-0000-0000-0000-000000000020', 'c1000000-0000-0000-0000-000000000010', 'voice_memo',
   'Ethan asked about bond ladder strategies and high-grade corporate bonds. He mentioned plans to travel extensively in retirement and needs reliable monthly cash flow.',
   NULL, '2025-02-25 14:45:00+00')
ON CONFLICT DO NOTHING;

-- -----------------------------------------------------------------------------
-- CLIENT CONTEXT  (2-3 per client = 22 total)
-- -----------------------------------------------------------------------------
INSERT INTO client_context (id, client_id, category, content, source_interaction_id) VALUES
  -- Oliver Bennett
  ('e1000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001', 'financial_goal',   'Plans to retire in 10 years; targeting capital preservation in final 3 years.',          'b1000000-0000-0000-0000-000000000001'),
  ('e1000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000001', 'family_event',     'Son started university; potential for increased expenses over the next 4 years.',        'b1000000-0000-0000-0000-000000000001'),
  ('e1000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000001', 'personal_interest','Annual family holiday to Italy planned for June.',                                        'b1000000-0000-0000-0000-000000000002'),

  -- Priya Mehta
  ('e1000000-0000-0000-0000-000000000004', 'c1000000-0000-0000-0000-000000000002', 'personal_interest','Strong preference for ESG and sustainable investment products.',                          'b1000000-0000-0000-0000-000000000003'),
  ('e1000000-0000-0000-0000-000000000005', 'c1000000-0000-0000-0000-000000000002', 'financial_goal',   'Expects large Q3 bonus; plans to invest the full amount.',                               'b1000000-0000-0000-0000-000000000004'),
  ('e1000000-0000-0000-0000-000000000006', 'c1000000-0000-0000-0000-000000000002', 'risk_tolerance',   'High risk tolerance; comfortable with aggressive growth strategies.',                    'b1000000-0000-0000-0000-000000000003'),

  -- Thomas Nguyen
  ('e1000000-0000-0000-0000-000000000007', 'c1000000-0000-0000-0000-000000000003', 'risk_tolerance',   'Very risk averse; capital preservation is the primary investment objective.',             'b1000000-0000-0000-0000-000000000005'),
  ('e1000000-0000-0000-0000-000000000008', 'c1000000-0000-0000-0000-000000000003', 'family_event',     'Wife recently diagnosed with illness; anticipates increased medical and care expenses.',  'b1000000-0000-0000-0000-000000000006'),

  -- Amelia Okafor
  ('e1000000-0000-0000-0000-000000000009', 'c1000000-0000-0000-0000-000000000004', 'financial_goal',   'Interested in REIT exposure to diversify away from business income.',                    'b1000000-0000-0000-0000-000000000007'),
  ('e1000000-0000-0000-0000-000000000010', 'c1000000-0000-0000-0000-000000000004', 'financial_goal',   'Wants to establish a family trust for estate planning; private equity interest.',        'b1000000-0000-0000-0000-000000000008'),

  -- Daniel Kowalski
  ('e1000000-0000-0000-0000-000000000011', 'c1000000-0000-0000-0000-000000000005', 'personal_interest','Relocated from Poland; values international portfolio diversification.',                  'b1000000-0000-0000-0000-000000000009'),
  ('e1000000-0000-0000-0000-000000000012', 'c1000000-0000-0000-0000-000000000005', 'financial_goal',   'Partial EUR income; seeks currency hedging and index fund strategy for retirement.',     'b1000000-0000-0000-0000-000000000010'),

  -- Sofia Andersen
  ('e1000000-0000-0000-0000-000000000013', 'c1000000-0000-0000-0000-000000000006', 'financial_goal',   'Plans to downsize home next year; sale proceeds to be reinvested for income.',           'b1000000-0000-0000-0000-000000000012'),
  ('e1000000-0000-0000-0000-000000000014', 'c1000000-0000-0000-0000-000000000006', 'risk_tolerance',   'Conservative; prefers dividend stocks and term deposits for steady retirement income.',  'b1000000-0000-0000-0000-000000000011'),

  -- Marcus Silva
  ('e1000000-0000-0000-0000-000000000015', 'c1000000-0000-0000-0000-000000000007', 'risk_tolerance',   'High risk tolerance; strong preference for emerging market exposure.',                   'b1000000-0000-0000-0000-000000000013'),
  ('e1000000-0000-0000-0000-000000000016', 'c1000000-0000-0000-0000-000000000007', 'personal_interest','Frequent business travel; currently expanding operations into Brazil.',                  'b1000000-0000-0000-0000-000000000014'),

  -- Yuki Tanaka
  ('e1000000-0000-0000-0000-000000000017', 'c1000000-0000-0000-0000-000000000008', 'financial_goal',   'Saving to purchase an investment property in approximately 3 years.',                   'b1000000-0000-0000-0000-000000000016'),
  ('e1000000-0000-0000-0000-000000000018', 'c1000000-0000-0000-0000-000000000008', 'personal_interest','Works in software engineering; interested in tech-sector-weighted growth portfolio.',    'b1000000-0000-0000-0000-000000000015'),

  -- Rachel O'Brien
  ('e1000000-0000-0000-0000-000000000019', 'c1000000-0000-0000-0000-000000000009', 'financial_goal',   'Maximising concessional super contributions; considering move to private practice.',     'b1000000-0000-0000-0000-000000000018'),
  ('e1000000-0000-0000-0000-000000000020', 'c1000000-0000-0000-0000-000000000009', 'personal_interest','Strong preference for ethical and ESG-aligned investments.',                             'b1000000-0000-0000-0000-000000000017'),

  -- Ethan Patel
  ('e1000000-0000-0000-0000-000000000021', 'c1000000-0000-0000-0000-000000000010', 'financial_goal',   'Requires reliable monthly income from portfolio to supplement pension in retirement.',  'b1000000-0000-0000-0000-000000000019'),
  ('e1000000-0000-0000-0000-000000000022', 'c1000000-0000-0000-0000-000000000010', 'personal_interest','Plans extensive international travel post-retirement; needs liquid, income-generating assets.', 'b1000000-0000-0000-0000-000000000020')
ON CONFLICT DO NOTHING;

-- -----------------------------------------------------------------------------
-- MESSAGE DRAFTS  (1 per client = 10 total, mix of statuses)
-- -----------------------------------------------------------------------------
INSERT INTO message_draft (id, client_id, trigger_type, generated_content, status) VALUES
  ('d1000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001', 'review_reminder',
   'Dear Oliver, I hope this message finds you well. I wanted to reach out ahead of your upcoming portfolio review scheduled for 15 September. Given recent market movements, it would be worth discussing your bond allocation and how your timeline to retirement is progressing. Please let me know a convenient time. Best regards, Sarah',
   'sent'),

  ('d1000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000002', 'market_update',
   'Hi Priya, I wanted to share a quick update on the ESG tech sector, which has performed strongly this quarter. This aligns well with your investment goals. I also wanted to flag some options for deploying your anticipated Q3 bonus — happy to walk you through a few scenarios at your convenience. Best, Sarah',
   'pending'),

  ('d1000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000003', 'review_reminder',
   'Dear Thomas, I hope you and your family are doing well. I wanted to connect ahead of our November review. With inflation remaining a key consideration for your portfolio, I have some updated analysis on TIPS and inflation-linked bonds I would like to share. Warm regards, Sarah',
   'pending'),

  ('d1000000-0000-0000-0000-000000000004', 'c1000000-0000-0000-0000-000000000004', 'portfolio_milestone',
   'Hi Amelia, congratulations on the Series B milestone — that is a fantastic achievement! I have been thinking about the estate planning and REIT diversification goals you raised. I have put together a few initial ideas I would love to walk you through when you have a moment. Regards, Sarah',
   'sent'),

  ('d1000000-0000-0000-0000-000000000005', 'c1000000-0000-0000-0000-000000000005', 'review_reminder',
   'Hi Daniel, just a reminder that your portfolio review is coming up in January. I have also done some initial modelling on EUR currency hedging options that I think would be very relevant to your situation. Looking forward to catching up. Best, Sarah',
   'pending'),

  ('d1000000-0000-0000-0000-000000000006', 'c1000000-0000-0000-0000-000000000006', 'review_reminder',
   'Dear Sofia, I hope you are well. As your October review approaches, I wanted to flag a few dividend reinvestment options and an update on term deposit rates that may interest you. I have also noted your upcoming property downsizing — it would be great to plan ahead for that. Warm regards, James',
   'sent'),

  ('d1000000-0000-0000-0000-000000000007', 'c1000000-0000-0000-0000-000000000007', 'market_update',
   'Hi Marcus, the emerging market outlook has shifted positively following recent central bank decisions, which should benefit your portfolio. I have also put together some thoughts on how a small crypto allocation might fit within your overall risk framework. Let me know when you are free to chat. Best, James',
   'pending'),

  ('d1000000-0000-0000-0000-000000000008', 'c1000000-0000-0000-0000-000000000008', 'review_reminder',
   'Hi Yuki, just a note ahead of your December review. Given your 3-year horizon for the property purchase, I would like to discuss a liquidity strategy that keeps your growth objectives intact while ensuring funds are accessible when you need them. Speak soon, James',
   'pending'),

  ('d1000000-0000-0000-0000-000000000009', 'c1000000-0000-0000-0000-000000000009', 'portfolio_milestone',
   'Dear Rachel, I hope the transition planning is going well. I have modelled a concessional contribution strategy that could significantly reduce your tax liability this financial year. Whenever you are ready to explore the private practice move further, I am here to help align your financial plan. Best regards, James',
   'sent'),

  ('d1000000-0000-0000-0000-000000000010', 'c1000000-0000-0000-0000-000000000010', 'review_reminder',
   'Dear Ethan, I hope retirement is treating you well! Your review is scheduled for late May. I have been looking at a bond ladder structure and a selection of high-grade corporates that could provide the monthly income flow you are looking for, while supporting your travel plans. Looking forward to catching up, James',
   'sent')
ON CONFLICT DO NOTHING;
