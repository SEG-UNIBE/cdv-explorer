# Bitcoin Improvement Proposal Network Graph <!-- omit from toc -->

![thumb](./assets/t0004-bip-mining.png)

- [Introduction](#introduction)
  - [Context](#context)
  - [Motivation](#motivation)
  - [Goal](#goal)
  - [Pointers](#pointers)
- [Next Steps](#next-steps)

> *Note: This TOC is generated automatically using VSCode and the «[Markdown All in One](https://marketplace.visualstudio.com/items?itemName=yzhang.markdown-all-in-one)» plugin. Work smart, not hard.*

&nbsp;

## Introduction

Bitcoin Improvement Proposals (BIPs) are essential to the evolution of the Bitcoin protocol, characterized by both their individual attributes (e.g., status, categories) and interrelationships (e.g., dependencies, succession).
This project aims to mine and structure BIP data, archiving it in a browsable format that captures both these characteristics and connections.
Through graph-based visualizations and analysis, we seek to enable a more interactive exploration of the BIP landscape, enhancing both understanding and insight into the proposals and their roles within the ecosystem.

### Context

Bitcoin is a decentralized, peer-to-peer electronic currency, continuously evolving through contributions from its open-source community.
At the heart of this development are Bitcoin Improvement Proposals (BIPs), which define the requirements and features that developers follow when implementing protocol changes.
BIPs guide the ongoing evolution of Bitcoin and serve to clearly identify and communicate proposed features within the ecosystem.

Graph databases, on the other hand, provide a powerful method for representing non-relational data, making it possible to explore both the individual characteristics and relationships between BIPs using advanced analytic tools and visualizations.
This project aims to combine BIPs and graph databases, offering new insights into the influence, structure, and interconnectedness of these proposals.

### Motivation

While BIPs follow a structured format, their current textual representation is limited in terms of interactive capabilities.
The static nature of browsing BIPs can obscure insights into their relationships and influence across the Bitcoin landscape.
By mining and organizing BIPs into a more dynamic format, we can facilitate a richer, more interactive browsing experience.
Additionally, through the use of graph analysis, it becomes possible to detect important features such as highly connected BIPs (key proposals), subgraphs, or clusters of related BIPs, providing a more holistic understanding of their influence and evolution within the Bitcoin ecosystem.

### Goal

The project is structured into three consecutive work packages, each building on the previous stage to achieve the overall goal of creating an interactive system for exploring BIPs through graph-based analysis:

1. **Design a BIP Archiving Schema:** Develop a structured data schema for archiving BIPs, addressing questions such as the categorization of BIPs (standard, information, process), consistent attributing, and perhaps even methods for breaking down BIPs into meaningful sub-components (e.g., summaries, examples, references).
The schema should also account for the various relationships between BIPs, such as dependencies and successions, ensuring that these are captured thoroughly.
2. **Develop the Mining Process:** Identify the suitable techniques for extracting structured information from the publicly available BIPs and converting it into the data schema.
While full automation may not be feasible, the goal is to explore semi-automatic methods that minimize manual effort while maximizing data accuracy and consistency.
3. **Visualize Mined Data Using Graphs:** Implement at least one method for interactive graph-based visualization of the mined BIP data.
Use standard graph analysis techniques (e.g., average connectivity, anomaly detection, subgraph discovery, etc.) to provide a comprehensive view of the BIP landscape.
The visualizations should make it easier to explore and understand the complex relationships and influences among BIPs.

### Pointers

What resources and other related work could help the student to work on this project?
This could be links to papers, lectures, websites, videos, etc.

- Antonopoulos, A.M.: [Mastering Bitcoin: Programming the Open Blockchain](https://github.com/bitcoinbook/bitcoinbook?tab=readme-ov-file#mastering-bitcoin). O’Reilly, Sebastopol, CA (2017).
- Definition of [Bitcoin Improvement Proposals](https://bitcoinwiki.org/wiki/bitcoin-improvement-proposals), bitcoinwiki.org
- [BIP2](https://github.com/bitcoin/bips/blob/master/bip-0002.mediawiki) explaining the BIP process
- [Complete list of BIPs](https://github.com/bitcoin/bips), github.com
- Bechberger, D., Perryman, J.: [Graph Databases in Action](https://www.amazon.com/Graph-Databases-Action-Dave-Bechberger/dp/1617296376). Manning, Shelter Island, New York (2020).
- Robinson, I., Webber, J., Eifrem, E.: [Graph Databases: New Opportunities for Connected Data](https://www.amazon.com/exec/obidos/ASIN/1491930896/acmorg-20). O’Reilly, Beijing Boston Farnham (2015).

## Next Steps

**First👉**
Familiarize yourself with the BIP world.
Start by reading [BIP2](https://github.com/bitcoin/bips/blob/master/bip-0002.mediawiki), a BIP that specifies the BIP workflow.
For example, it specifies how the header preamble should look like (see quote below).

> Each BIP must begin with an RFC 822 style header preamble.
> The headers must appear in the following order. Headers marked with "*" are optional and are described below.
> All other headers are required.
>
>```text
>   BIP:              <BIP number, or "?" before being assigned>
>* Layer:            <Consensus (soft fork) | Consensus (hard fork) | 
>                     Peer Services | API/RPC | Applications>
>   Title:            <BIP title; maximum 44 characters>
>   Author:           <list of authors' real names and email addrs>
>* Discussions-To:   <email address>
>* Comments-Summary: <summary tone>
>   Comments-URI:     <links to wiki page for comments>
>   Status:           <Draft | Active | Proposed | Deferred | Rejected | 
>                     Withdrawn | Final | Replaced | Obsolete>
>   Type:             <Standards Track | Informational | Process>
>   Created:          <date created on, in ISO 8601 (yyyy-mm-dd) format>
>   License:          <abbreviation for approved license(s)>
>* License-Code:     <abbreviation for code under different
>                     approved license(s)>
>* Post-History:     <dates of postings to bitcoin mailing list,
>                     or link to thread in mailing list archive>
>* Requires:         <BIP number(s)>
>* Replaces:         <BIP number>
>* Superseded-By:    <BIP number>
>```

Continue by reading BIP123 which discusses BIP classification matters.
Wrap up your BIP experience with this bitcoinwiki article about BIPs.

The primary source for BIP documents is the [BIP catalog on GitHub](https://github.com/bitcoin/bips).
In case you don't want to navigate on GitHub all the time, note that there exist other sites for browsing BIPs.
For example, [bips.dev](https://bips.dev/) wraps a nicer user-interface around it.
The way how bips.dev is developed might be also interesting for you (check out its [repo](https://github.com/nickmonad/bips.dev)).
Yet another (probably bit wacky) way to explore BIPs is the [en.bitcoin.it/wiki](https://en.bitcoin.it/wiki/Category:BIP).
You see, the *Bitcoin idea* is recorded in several locations throughout the internet.

**Second👉**
Do some desk research on BIP graph visualizations.
Propably there has been some work with similar goals.
If so, it is important to find these works and analyse (1) what they do, (2) how they do it, and (3) how we are going to do things better.

**Third👉**
Think about system architecture of your crawler application.
Use this repo ([SEG-UNIBE/bipng](https://github.com/SEG-UNIBE/bipng)) for both your code and documentation/presentation.
As inspiration how this could look like, see [a seminar project that I once did](https://github.com/RomanBoegli/godbbench).

As discussed, your crawler shall focus on the primary source of BIP documents i.e. `github.com/bitcoin/bips`.
Investigate into possibilities how you could deploy e.g. a Python script using *GitHub Actions* to some sever (e.g. [Heroku](https://www.heroku.com/), [Railway](https://railway.app/new), [Render](https://render.com/), [Fly.io](https://fly.io/), ...).
Also think about suitable database management systems to archive the crawled data.
So-called NoSQL DBMS like MongoDB may be a great option for this use case.
But also validate the suitability of graph-based DBMS like [Neo4j](https://neo4j.com/product/neo4j-graph-database/).

**Fourth👉**
We talk again. Meeting invite is coming.
