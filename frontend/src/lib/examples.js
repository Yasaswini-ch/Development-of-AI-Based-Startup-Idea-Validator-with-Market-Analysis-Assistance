// Sample ideas the form can fill in with one click, so a first-time visitor
// can see how much detail a good submission has: who the user is, who pays,
// how it works, the first market and a rough price. They are inputs only -
// nothing here is a result. Each stays inside the API's limits (idea 2,500
// characters, customer 600, problem 1,500).
export const SAMPLE_IDEAS = [
  {
    label: 'Support call digest',
    idea:
      'CallDigest connects to a company\'s support phone and chat tools, transcribes recorded customer calls, and groups them by theme. Every Monday it sends product managers a one-page digest: the five most repeated complaints with the exact customer quotes, how many calls mentioned each, and whether the count rose or fell versus last month. Managers can click a theme to hear the original clips. We start with B2B SaaS companies that have 10 to 50 support agents and charge a flat monthly fee per agent seat, with a pilot on one support queue.',
    targetCustomer:
      'Product managers and heads of support at B2B SaaS companies with 10 to 50 support agents. Support leads use it daily; the product or customer-success VP signs off on the budget.',
    problem:
      'Support agents hear the same product complaints every day, but the feedback stays in call recordings nobody has time to listen to. Product teams rely on a few anecdotes and a ticket tag that agents fill in inconsistently, so recurring problems stay unfixed and are only noticed when customers cancel.',
  },
  {
    label: 'Neighbourhood plant swaps',
    idea:
      'LeafLoop is a mobile app where people in the same neighbourhood list houseplants and cuttings they want to give away or swap. Users photograph a plant, the app identifies it and suggests care tips, and shows matching offers within walking distance. Swaps are arranged in the app, with a rating after each exchange and public meet-up spots such as cafes and community gardens. It is free for swapping; we plan to earn from a small subscription for rare-plant alerts and from partnerships with local garden shops. We would launch in two dense apartment-heavy neighbourhoods.',
    targetCustomer:
      'Urban apartment dwellers aged 22 to 40 who keep several houseplants, follow plant accounts on social media, and live within a few kilometres of other plant owners.',
    problem:
      'Houseplants are expensive and a single plant often grows far more cuttings than its owner can use, so healthy cuttings are thrown away. People who want a particular plant have no trusted local way to find one, and plant groups on social media are scattered, slow and full of people who live too far away.',
  },
  {
    label: 'Investor update copilot',
    idea:
      'RunwayNote connects to a startup\'s accounting, billing and product analytics tools, pulls the month\'s numbers (revenue, burn, runway, growth, key product metrics), and drafts the monthly investor update in the founder\'s own voice: headline wins, asks, metrics with a plain-language explanation of every big change, and a short list of risks. The founder reviews and edits the draft, then sends it from the app, which also tracks which investors opened it and replied. We would start with seed-stage founders on a flat monthly price, and sell a team plan to small venture funds later.',
    targetCustomer:
      'Seed and pre-seed startup founders with one to three investors and no finance or operations hire. The founder is both the user and the buyer.',
    problem:
      'Writing a good investor update takes three to five hours of copying numbers between tools and finding words, so founders skip months or send vague updates. Investors then hear about problems late, lose confidence, and are slower to help or to put money into the next round.',
  },
  {
    label: 'Freelancer invoicing',
    idea:
      'ChaseFree is an invoicing app for solo freelancers and tiny agencies. It creates invoices from tracked hours, sends them, and then follows up on late payments automatically with a polite sequence: a friendly reminder before the due date, a firmer note after, and a final notice with late-fee wording the freelancer approved in advance. It shows a simple cash-flow forecast from unpaid invoices and flags clients who are repeatedly late. Free for up to three clients a month, then a flat monthly plan, with an optional small fee for same-day payouts.',
    targetCustomer:
      'Solo freelancers (designers, developers, writers, consultants) and agencies of up to five people who invoice 5 to 30 clients a month and handle their own billing without an accountant.',
    problem:
      'Chasing unpaid invoices is awkward and takes hours each month, so many freelancers wait too long or never follow up. Late payments leave them short on rent and tax money, and they avoid raising it with a client for fear of damaging the relationship.',
  },
]
