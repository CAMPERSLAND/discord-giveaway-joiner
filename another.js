client.on('message', async message => {
    if (message.content.includes('**GIVEAWAY**')) {
        var giveawaybot = '294882584201003009';
        if (message.author.id === giveawaybot) {
            setTimeout(() => message.react('?'), 1000);
            console.log(`Giveaway Reaction Added Successfully !`)
            console.log(`[GUILD] : ${message.guild}`)
            console.log(`[CHANNEL] : ${message.channel.name}`)
            var embed = new Discord.RichEmbed()
                .setColor('RANDOM')
                .setTitle('Giveaway Joined')
                .addField('[GUILD] :', `**${message.guild}**`)
                .addField('[CHANNEL] :', `**${message.channel.name}**`)
                .addField('[Message Link] :', `${message.url}`)
            client.guilds.get('GUILD_ID').channels.get('CHANNEL_ID').send(embed)
        }
        else return;
    }
});