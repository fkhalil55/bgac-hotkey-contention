'use strict';
// Caliper 0.5 workload for the bgac-contention chaincode.
// All experiment parameters come from the round's `arguments` block,
// which scripts/gen_configs.py writes. Each round uses fresh actor IDs
// (RUN_ID + round tag), so rounds never share counter keys.
//
// strategy "deltackpt" (E5) = chaincode strategy "deltawrite" plus an
// off-chain monitor: every `ckpt` calls the client queries the actor's delta
// count (read-only) and, once it reaches the limit, submits one write-only
// "block" transaction. ckpt = 0 means no monitor (pure deltawrite).
const { WorkloadModuleBase } = require('@hyperledger/caliper-core');

class ContentionWorkload extends WorkloadModuleBase {
  async initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext) {
    await super.initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext);
    const a = roundArguments;
    this.strategy   = a.strategy;
    this.ccStrategy = a.strategy === 'deltackpt' ? 'deltawrite' : a.strategy;
    this.partitions = a.strategy === 'deltackpt' ? '1' : String(a.partitions);
    this.ckpt       = a.strategy === 'deltackpt' ? Number(a.partitions) : 0;
    this.limit      = String(a.limit);
    this.bucketSecs = String(a.bucketSecs || 0);
    this.actors     = Number(a.actors);
    this.peers      = a.targetPeers;            // array of peer names
    this.runTag     = `${process.env.RUN_ID || 'run'}-${a.tag}`;
    this.txIndex    = 0;
    this.blocked    = false;
  }

  base(fn, args, readOnly) {
    return { contractId: 'bgac-contention', channel: 'appchannel', contractFunction: fn,
             contractArguments: args, invokerIdentity: 'Admin', targetPeers: this.peers, readOnly };
  }

  async submitTransaction() {
    const actor = `${this.runTag}-a${this.txIndex % this.actors}`;
    this.txIndex++;
    if (this.ckpt > 0 && this.txIndex % this.ckpt === 0 && !this.blocked) {
      const res = await this.sutAdapter.sendRequests(this.base('count', [actor, this.bucketSecs], true));
      const st = Array.isArray(res) ? res[0] : res;
      const raw = st && typeof st.GetResult === 'function' ? st.GetResult() : undefined;
      const n = parseInt(raw ? raw.toString() : 'NaN', 10);
      if (Number.isNaN(n)) { console.warn(`[deltackpt] could not read count result for ${actor}`); return; }
      if (n >= Number(this.limit)) {
        this.blocked = true;
        console.log(`[deltackpt] ${this.runTag} count=${n} at call ${this.txIndex}: sending block`);
        await this.sutAdapter.sendRequests(this.base('block', [actor, this.bucketSecs], false));
      }
      return;
    }
    await this.sutAdapter.sendRequests(this.base('request',
      [this.ccStrategy, actor, this.partitions, this.limit, this.bucketSecs, this.runTag], false));
  }
}

module.exports.createWorkloadModule = () => new ContentionWorkload();
