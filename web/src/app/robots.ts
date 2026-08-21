import type { MetadataRoute } from 'next';
import { env } from '@/env';

export default function robots(): MetadataRoute.Robots {
  const site = env.NEXT_PUBLIC_SITE_URL.replace(/\/$/, '');
  return {
    rules: { userAgent: '*', allow: '/', disallow: ['/desk', '/api/'] },
    sitemap: `${site}/sitemap.xml`,
  };
}
