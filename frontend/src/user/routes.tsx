import { Routes, Route, useParams } from "react-router-dom";
import { ChatListPage } from "./pages/ChatListPage";
import { CharacterSetupPage } from "./pages/CharacterSetupPage";
import { ChatViewPage } from "./pages/ChatViewPage";
import { WorldPage } from "./pages/WorldPage";

const WorldPageRoute = () => {
  const { worldId } = useParams<{ worldId: string }>();
  return <WorldPage key={worldId} />;
};

const CharacterSetupPageRoute = () => {
  const { worldId } = useParams<{ worldId: string }>();
  return <CharacterSetupPage key={worldId} />;
};

const ChatViewPageRoute = () => {
  const { chatId } = useParams<{ chatId: string }>();
  return <ChatViewPage key={chatId} />;
};

export function UserRoutes() {
  return (
    <Routes>
      <Route path="/" element={<ChatListPage />} />
      <Route path="/worlds/:worldId" element={<WorldPageRoute />} />
      <Route path="/worlds/:worldId/new" element={<CharacterSetupPageRoute />} />
      <Route path="/chat/:chatId" element={<ChatViewPageRoute />} />
    </Routes>
  );
}
