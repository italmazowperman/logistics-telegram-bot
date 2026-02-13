require('dotenv').config();
const { Telegraf } = require('telegraf');
const { Pool } = require('pg');

// Подключение к Supabase
const pool = new Pool({
  connectionString: process.env.SUPABASE_DB_URL,
  ssl: { rejectUnauthorized: false }
});

const bot = new Telegraf(process.env.BOT_TOKEN);

bot.start((ctx) => ctx.reply('Добро пожаловать! Используйте /help для списка команд.'));
bot.help((ctx) => ctx.reply(
  'Доступные команды:\n' +
  '/orders - список активных заказов\n' +
  '/report - сводный отчёт\n' +
  '/order_123 - информация о заказе №123\n' +
  '/tasks_123 - задачи по заказу №123'
));

bot.command('orders', async (ctx) => {
  try {
    const res = await pool.query(
      `SELECT "OrderNumber", "ClientName", "Status", "EtaDate" 
       FROM public."Orders" 
       WHERE "Status" NOT IN ('Completed','Cancelled')
       ORDER BY "OrderNumber"`
    );
    if (res.rows.length === 0) return ctx.reply('Нет активных заказов.');
    let msg = '📦 **Активные заказы:**\n\n';
    res.rows.forEach(o => {
      msg += `• ${o.OrderNumber} — ${o.ClientName}\n  Статус: ${o.Status}, ETA: ${o.EtaDate ? new Date(o.EtaDate).toLocaleDateString('ru') : 'не указано'}\n`;
    });
    ctx.reply(msg);
  } catch (err) {
    console.error(err);
    ctx.reply('Ошибка получения заказов.');
  }
});

bot.command('report', async (ctx) => {
  try {
    const total = await pool.query(`SELECT COUNT(*) FROM public."Orders"`);
    const active = await pool.query(`SELECT COUNT(*) FROM public."Orders" WHERE "Status" NOT IN ('Completed','Cancelled')`);
    const containers = await pool.query(`SELECT SUM("ContainerCount") FROM public."Orders"`);
    const weight = await pool.query(`SELECT SUM(c."Weight") FROM public."Containers" c`);
    ctx.reply(
      `📊 **Сводный отчёт**\n\n` +
      `Всего заказов: ${total.rows[0].count}\n` +
      `Активных: ${active.rows[0].count}\n` +
      `Контейнеров: ${containers.rows[0].sum || 0}\n` +
      `Общий вес: ${weight.rows[0].sum || 0} кг`
    );
  } catch (err) {
    console.error(err);
    ctx.reply('Ошибка формирования отчёта.');
  }
});

// Динамические команды
bot.use(async (ctx, next) => {
  const text = ctx.message?.text;
  if (!text) return next();

  const orderMatch = text.match(/^\/order_(\d+)$/);
  if (orderMatch) {
    const id = orderMatch[1];
    try {
      const order = await pool.query(
        `SELECT * FROM public."Orders" WHERE "OrderNumber" = $1 OR "Id" = $1::int`,
        [id]
      );
      if (order.rows.length === 0) return ctx.reply('Заказ не найден.');
      const o = order.rows[0];
      let msg = `🔹 **Заказ ${o.OrderNumber}**\n`;
      msg += `Клиент: ${o.ClientName}\n`;
      msg += `Тип груза: ${o.GoodsType || '—'}\n`;
      msg += `Маршрут: ${o.Route || '—'}\n`;
      msg += `Контейнеров: ${o.ContainerCount}\n`;
      msg += `Статус: ${o.Status}\n`;
      msg += `ETA: ${o.EtaDate ? new Date(o.EtaDate).toLocaleDateString('ru') : '—'}\n`;
      msg += `TKM дата: ${o.TkmDate ? new Date(o.TkmDate).toLocaleDateString('ru') : '—'}`;
      ctx.reply(msg);
    } catch (err) {
      ctx.reply('Ошибка получения заказа.');
    }
    return;
  }

  const tasksMatch = text.match(/^\/tasks_(\d+)$/);
  if (tasksMatch) {
    const id = tasksMatch[1];
    try {
      const tasks = await pool.query(
        `SELECT t.*, o."OrderNumber" 
         FROM public."Tasks" t 
         JOIN public."Orders" o ON t."OrderId" = o."Id" 
         WHERE o."OrderNumber" = $1 OR o."Id" = $1::int`,
        [id]
      );
      if (tasks.rows.length === 0) return ctx.reply('Нет задач для этого заказа.');
      let msg = `📋 **Задачи по заказу ${tasks.rows[0].OrderNumber}:**\n\n`;
      tasks.rows.forEach(t => {
        const status = ['🔴 To Do', '🟡 In Progress', '✅ Completed'][t.Status] || 'Неизвестно';
        msg += `• ${t.Description}\n  ${status}, срок: ${t.DueDate ? new Date(t.DueDate).toLocaleDateString('ru') : '—'}\n`;
      });
      ctx.reply(msg);
    } catch (err) {
      ctx.reply('Ошибка получения задач.');
    }
    return;
  }

  next();
});

// Запуск бота (long polling)
bot.launch().then(() => console.log('Telegram bot started'));

// Graceful stop
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
