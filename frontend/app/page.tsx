import SubmissionNote from "@/components/photo-guide";
import PhotoStudio from "@/components/photo-studio/photo-studio";
import SiteFooter from "@/components/site-footer";
import SiteHeader from "@/components/site-header";

export default function Home() {
  return (
    <main>
      <SiteHeader />
      <PhotoStudio />
      <SubmissionNote />
      <SiteFooter />
    </main>
  );
}
