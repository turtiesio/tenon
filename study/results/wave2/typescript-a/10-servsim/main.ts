import { readFileSync } from 'node:fs';

const args = process.argv.slice(2);
let capacity = Infinity;
const positional: string[] = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === '-q') {
    const value = args[++i];
    if (!/^[0-9]{1,7}$/.test(value ?? '')) process.exit(2);
    capacity = Number(value);
  } else if (args[i].startsWith('-')) process.exit(2);
  else positional.push(args[i]);
}
if (positional.length !== 1 || !/^[0-9]{1,4}$/.test(positional[0]) || Number(positional[0]) < 1 || Number(positional[0]) > 1000) process.exit(2);
const n = Number(positional[0]);
type Request = { id: string; arrival: number; duration: number };
const requests: Request[] = [];
const ids = new Set<string>();
let previous = -1;
for (let line of readFileSync(0, 'utf8').split('\n')) {
  line = line.replace(/\r$/, '');
  if (/^ *$/.test(line)) continue;
  const match = /^([A-Za-z0-9_-]{1,16}) ([0-9]{1,12}) ([0-9]{1,9})$/.exec(line);
  if (!match || ids.has(match[1]) || Number(match[2]) < previous || Number(match[3]) < 1) {
    console.error('Invalid trace');
    process.exit(1);
  }
  ids.add(match[1]);
  previous = Number(match[2]);
  requests.push({ id: match[1], arrival: previous, duration: Number(match[3]) });
}
type Server = { request?: Request; finish: number; busy: number; served: number };
const servers: Server[] = Array.from({ length: n }, () => ({ finish: Infinity, busy: 0, served: 0 }));
const queue: Request[] = [];
const output: string[] = [];
let head = 0, next = 0, served = 0, rejected = 0, maxWait = 0, totalWait = 0n, makespan = 0;
function start(request: Request, index: number, time: number): void {
  const server = servers[index];
  server.request = request;
  server.finish = time + request.duration;
  server.busy += request.duration;
  server.served++;
  served++;
  const wait = time - request.arrival;
  totalWait += BigInt(wait);
  maxWait = Math.max(maxWait, wait);
  output.push(`${time} start ${request.id} s${index + 1} wait=${wait}`);
}
while (true) {
  let time = requests[next]?.arrival ?? Infinity;
  for (const server of servers) time = Math.min(time, server.finish);
  if (time === Infinity) break;
  for (let k = 0; k < n; k++) {
    const server = servers[k];
    if (server.finish !== time) continue;
    output.push(`${time} done ${server.request!.id} s${k + 1}`);
    makespan = time;
    server.request = undefined;
    server.finish = Infinity;
    if (head < queue.length) start(queue[head++], k, time);
  }
  while (next < requests.length && requests[next].arrival === time) {
    const request = requests[next++];
    const idle = servers.findIndex(server => server.request === undefined);
    if (idle >= 0) start(request, idle, time);
    else if (queue.length - head < capacity) queue.push(request);
    else {
      rejected++;
      output.push(`${time} reject ${request.id}`);
    }
  }
}
output.push(`served=${served} rejected=${rejected} max_wait=${maxWait} total_wait=${totalWait} makespan=${makespan}`);
for (const [index, server] of servers.entries()) output.push(`s${index + 1} busy=${server.busy} served=${server.served}`);
process.stdout.write(output.join('\n') + '\n');
