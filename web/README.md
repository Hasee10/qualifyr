# CRM Dashboard

A modern CRM (Customer Relationship Management) dashboard built with **Next.js 16**, **TypeScript**, **Tailwind CSS v4**, and **shadcn/ui**.

![CRM Dashboard Preview](./Screenshot.png)

## Features

- **Dashboard Overview** - View key metrics at a glance
- **Revenue Analytics** - Interactive bar charts showing monthly revenue and deals
- **Deals Management** - Track deal progress with status badges and progress bars
- **Customer List** - Top customers ranked by revenue
- **Responsive Design** - Works seamlessly on desktop, tablet, and mobile
- **Dark/Light Mode** - Toggle between themes with automatic CSS variable switching
- **Sidebar Navigation** - Collapsible sidebar for mobile devices

## Tech Stack

- [Next.js 16](https://nextjs.org) - React framework with App Router
- [TypeScript](https://www.typescriptlang.org/) - Type-safe JavaScript
- [Tailwind CSS v4](https://tailwindcss.com/) - Utility-first CSS
- [shadcn/ui](https://ui.shadcn.com/) - Beautiful, accessible components
- [Recharts](https://recharts.org/) - Composable charting library
- [Lucide React](https://lucide.dev/) - Beautiful icons

## Getting Started

### Prerequisites

- Node.js 18+ installed
- npm, yarn, pnpm, or bun

### Installation

```bash
# Clone the repository
git clone https://github.com/ceyhanmolla/shadcn-crm-dashboard.git
cd shadcn-crm-dashboard

# Install dependencies
npm install

# Start the development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Project Structure

```
src/
├── app/
│   ├── globals.css      # Global styles and CSS variables
│   ├── layout.tsx       # Root layout with fonts
│   └── page.tsx         # Main dashboard page
├── components/
│   └── ui/              # shadcn/ui components
└── lib/
    └── utils.ts         # Utility functions
```

## Components Used

- `Card` - Display stats and charts
- `Table` - Show deals and customers
- `Avatar` - User and customer avatars
- `Badge` - Status indicators
- `Chart` - Revenue visualization
- `Tabs` - Navigation between sections
- `Progress` - Deal progress tracking
- `Separator` - Visual dividers
- `Sheet` - Mobile sidebar
- `Button` - Interactive elements
- `Input` - Search functionality

## License

MIT License - feel free to use this project for personal or commercial purposes.