function love.conf(t)
  t.identity = "BrassJanissary2"
  t.version = "11.5"
  t.window.title = "Латунный янычар 2.0"
  t.window.icon = "assets/gfx/ui/icon_512.png"
  t.window.width = 1920
  t.window.height = 1080
  t.window.resizable = true
  -- (р.25) В браузере окно — это вкладка, и на телефоне в альбомной
  -- ориентации она ниже 540 px. С минимумом 960×540 SDL держал канвас
  -- 960×540, CSS ужимал его в экран, и кадр выходил сплющенным (клики при
  -- этом попадали — SDL пересчитывает). Letterbox в main.lua впишет мир в
  -- окно любого размера, поэтому в вебе минимум снят. love._os выставляет
  -- движок до conf.lua; «Web» — так себя называет love.js.
  if love._os ~= "Web" then
    t.window.minwidth = 960
    t.window.minheight = 540
  end
  t.window.vsync = 1
  t.console = false
end
