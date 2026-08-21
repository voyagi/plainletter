import type { MetadataRoute } from 'next';
import { env } from '@/env';

// The console is left out on purpose: it is a working surface holding someone's letter, not a page
// to be found in a search result.
export default function sitemap(): MetadataRoute.Sitemap {
  const site = env.NEXT_PUBLIC_SITE_URL.replace(/\/$/, '');
  return [
    { url: `${site}/`, changeFrequency: 'monthly', priority: 1 },
    { url: `${site}/privacy`, changeFrequency: 'yearly', priority: 0.5 },
    { url: `${site}/sample-card`, changeFrequency: 'yearly', priority: 0.3 },
  ];
}
